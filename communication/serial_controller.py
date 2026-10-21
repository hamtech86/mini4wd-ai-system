"""
Serial Controller Interface
MOTOR_BREAKIN_V3

Break-in Controller <-> Arduino communication layer.

Arduino firmware MOTOR_BREAKIN_V3.00 protocol:
  FWD
  REV
  PWM=<0..255>
  STOP
"""

try:
    import serial
except ImportError:
    serial = None

import time
import re

from communication.raw_log_collector import RawLogCollector
from communication.csv_parser import CSVParser


class SerialController:

    def __init__(self, serial_port="/dev/ttyACM0", baudrate=57600):
        self.serial_port = serial_port
        self.baudrate = baudrate
        self.serial = None
        self.connected = False
        self.last_pwm = 0
        self.direction = "FWD"
        self.command_log = []
        self.last_raw_data = None
        self.raw_log_collector = RawLogCollector()
        self.parser = CSVParser()
        self.identity_verified = False
        self.device_info = None
        self.identity_error = "INFO identity has not been verified."

    @property
    def raw_log(self):
        """Exact raw serial text captured for the current measurement."""
        return self.raw_log_collector.snapshot()

    @property
    def has_raw_log(self):
        return self.raw_log_collector.has_data

    def reset_raw_log(self):
        """Start a new raw-log capture for the next measurement."""
        self.raw_log_collector.reset()

    def freeze_raw_log(self):
        """Return the current measurement capture and discard the live buffer."""
        snapshot = self.raw_log_collector.snapshot()
        self.raw_log_collector.reset()
        return snapshot

    def connect(self):
        # Every new connection invalidates prior identity verification.
        self.identity_verified = False
        self.device_info = None
        self.identity_error = "INFO identity has not been verified."
        if serial is None:
            return False

        try:
            self.serial = serial.Serial(self.serial_port, self.baudrate, timeout=1)
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            time.sleep(2.0)
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            self.raw_log_collector.reset()
            self.connected = True
            self.identity_error = "INFO response not received."
            print("SERIAL CONNECTED", self.serial_port, self.baudrate)
            self.send_command("INFO")
            self._verify_info_response(timeout=1.0)
            # Port connectivity and device identity are separate states.
            return True
        except Exception as e:
            print("SERIAL CONNECT ERROR", e)
            self.connected = False
            self.identity_verified = False
            self.device_info = None
            self.identity_error = "Serial connection failed: " + str(e)
            return False

    def _verify_info_response(self, timeout=1.0):
        """Require an explicit valid INFO response before enabling drive commands."""
        deadline = time.monotonic() + max(0.0, float(timeout))
        while self.connected and self.serial and time.monotonic() < deadline:
            try:
                if not getattr(self.serial, "in_waiting", 0):
                    time.sleep(0.01)
                    continue
                original_timeout = getattr(self.serial, "timeout", None)
                try:
                    self.serial.timeout = max(0.0, deadline - time.monotonic())
                    decoded = self.serial.readline().decode("utf-8", errors="replace")
                finally:
                    self.serial.timeout = original_timeout
            except Exception as exc:
                self.identity_error = "INFO read failed: " + str(exc)
                self.identity_verified = False
                return False
            if not decoded:
                continue
            line = decoded.strip()
            if not line:
                continue
            if line.startswith("INFO"):
                try:
                    info = self.parser.parse(line)
                    self._validate_info_record(info)
                    return True
                except (ValueError, KeyError) as exc:
                    self.identity_verified = False
                    self.device_info = None
                    self.identity_error = "Invalid INFO identity: " + str(exc)
                    return False
            self.raw_log_collector.append(decoded)
            if line.startswith("DATA,"):
                self.last_raw_data = line
        self.identity_verified = False
        self.device_info = None
        self.identity_error = "INFO response timed out."
        return False

    def _validate_info_record(self, info):
        if info.get("record_type") != "INFO":
            raise ValueError("Unexpected record type")
        if info.get("TYPE") != "MOTOR" or info.get("MODEL") != "MOTOR_BREAKIN_V3":
            raise ValueError("Unexpected motor device identity")
        for key in ("FW", "BUILD", "ID"):
            if not isinstance(info.get(key), str) or not info[key].strip():
                raise ValueError("Invalid " + key)
        if not re.fullmatch(r"\d+(?:\.\d+)+", info["FW"]):
            raise ValueError("Invalid FW version")
        if not re.fullmatch(r"[A-Za-z0-9._-]{1,64}", info["BUILD"]):
            raise ValueError("Invalid BUILD identifier")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", info["ID"]):
            raise ValueError("Invalid device ID")
        self.device_info = {key: info[key] for key in ("TYPE", "MODEL", "FW", "BUILD", "ID")}
        self.identity_verified = True
        self.identity_error = ""
        return True

    def forward(self):
        self.direction = "FWD"
        return self.send_command("FWD")

    def reverse(self):
        self.direction = "REV"
        return self.send_command("REV")

    def set_pwm(self, pwm):
        requested_pwm = max(0, min(255, int(pwm)))
        result = self.send_command(f"PWM={requested_pwm}")
        # Do not report a blocked/unwritten command as the active output.
        if result is not False:
            self.last_pwm = requested_pwm
        return result

    def stop_breakin(self):
        self.set_pwm(0)
        return self.send_command("STOP")

    def emergency_stop(self):
        """Best-effort STOP sequence; successful writes do not prove physical stop."""
        was_connected = bool(self.connected and self.serial)
        errors = []

        # Try each safety action independently: a failed PWM=0 write must not
        # prevent the explicit STOP command or serial cleanup from being tried.
        try:
            if self.set_pwm(0) is False:
                errors.append(("PWM=0", RuntimeError("command was not sent")))
        except Exception as exc:
            errors.append(("PWM=0", exc))
            print("EMERGENCY STOP WARNING (PWM=0):", exc)

        try:
            if self.send_command("STOP") is False:
                errors.append(("STOP", RuntimeError("command was not sent")))
        except Exception as exc:
            errors.append(("STOP", exc))
            print("EMERGENCY STOP WARNING (STOP):", exc)

        try:
            self.disconnect()
        except Exception as exc:
            errors.append(("disconnect", exc))
            print("EMERGENCY STOP WARNING (disconnect):", exc)
        finally:
            # Keep software connection state fail-closed even if close() raises.
            self.serial = None
            self.connected = False
            self.identity_verified = False
            self.device_info = None
            self.identity_error = "Disconnected after emergency STOP; identity verification reset."

        # True means writes/cleanup raised no exceptions and a connection was
        # present at entry. It is NOT firmware acknowledgement or physical-stop proof.
        return was_connected and not errors

    def disconnect(self):
        serial_handle = self.serial
        try:
            if serial_handle:
                serial_handle.close()
        finally:
            self.serial = None
            self.connected = False
            self.identity_verified = False
            self.device_info = None
            self.identity_error = "Disconnected; identity verification reset."

    def send_command(self, command):
        self.command_log.append(command)
        print("SERIAL TX:", command)
        normalized = str(command).strip().upper()
        drive_command = normalized in ("START", "FWD", "REV", "RESUME") or (
            normalized.startswith("PWM=") and normalized != "PWM=0"
        )
        if drive_command and not self.identity_verified:
            self.identity_error = "Drive command blocked: INFO identity is not verified."
            print("SERIAL TX BLOCKED:", command, self.identity_error)
            return False
        if self.connected and self.serial:
            self.serial.write((command + "\n").encode("utf-8"))
            return command
        return False

    def read_measurement(self):
        """Read the newest DATA frame and retain the exact raw CSV string."""
        if not (self.connected and self.serial):
            return None

        latest_data = None
        while self.serial.in_waiting:
            raw = self.serial.readline()
            decoded = raw.decode("utf-8", errors="replace")
            if not decoded:
                continue
            self.raw_log_collector.append(decoded)
            line = decoded.strip()
            if not line:
                continue
            print("SERIAL RX:", line)
            if line.startswith("DATA,"):
                latest_data = line

        if latest_data is not None:
            self.last_raw_data = latest_data

        return latest_data
