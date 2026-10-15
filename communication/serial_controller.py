"""
Serial Controller Interface
MOTOR_BREAKIN_V3

Break-in Controller <-> Arduino communication layer.

Motor commands are gated by a validated connection-time INFO response.
INFO is connection metadata, never part of a newly captured RawLog body.
"""

from collections import deque
import math
import re
import threading
import time

try:
    import serial
except ImportError:
    serial = None

from communication.raw_log_collector import RawLogCollector
from communication.csv_parser import CSVParser


class SerialController:
    INFO_TIMEOUT_SEC = 1.0
    ALLOWED_MODELS = frozenset({"MOTOR_BREAKIN_V3"})
    REQUIRED_INFO_FIELDS = ("TYPE", "MODEL", "FW", "BUILD", "ID")
    SAFE_UNIDENTIFIED_COMMANDS = frozenset({
        "INFO", "STATUS", "PING", "STOP", "PAUSE", "PWM=0", "VCTRL=OFF",
    })
    READ_ONLY_COMMANDS = frozenset({"INFO", "STATUS", "PING"})
    SIMPLE_COMMANDS = frozenset({
        "INFO", "STATUS", "PING", "START", "STOP", "PAUSE", "RESUME", "FWD", "REV",
        "VCTRL=ON", "VCTRL=OFF",
    })

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
        self.csv_parser = CSVParser()
        self.device_info = None
        self.identity_error = "not_connected"
        self._identity_confirmed = False
        self._pending_rx_lines = deque()
        # INFO acquisition and measurement reads share one receive lock so
        # only one code path owns the serial RX stream at a time.
        self._rx_lock = threading.Lock()

    @property
    def identified(self):
        return bool(self.connected and self._identity_confirmed and self.device_info)

    def require_identified_device(self):
        """Raise before any run/session/state change unless INFO was validated."""
        if not self.identified:
            reason = self.identity_error or "device identity is unconfirmed"
            raise RuntimeError(f"Motor device is not identified: {reason}")

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

    def _clear_identity(self, reason):
        self.device_info = None
        self._identity_confirmed = False
        self.identity_error = reason

    @classmethod
    def _parse_info_line(cls, line):
        """Parse and validate one INFO line without accepting partial metadata."""
        text = line.strip()
        if not text.startswith("INFO,"):
            raise ValueError("Malformed INFO response")
        fields = {}
        for item in text.split(",")[1:]:
            if "=" not in item:
                raise ValueError("Malformed INFO field")
            key, value = item.split("=", 1)
            key = key.strip().upper()
            value = value.strip()
            if not key or not value:
                raise ValueError("Empty INFO key/value")
            if key in fields:
                # Duplicate keys are ambiguous even when values happen to match.
                raise ValueError(f"Duplicate INFO key: {key}")
            fields[key] = value
        missing = [key for key in cls.REQUIRED_INFO_FIELDS if not fields.get(key)]
        if missing:
            raise ValueError("Missing required INFO fields: " + ", ".join(missing))
        if fields["TYPE"] != "MOTOR":
            raise ValueError(f"Unsupported device TYPE: {fields['TYPE']}")
        if fields["MODEL"] not in cls.ALLOWED_MODELS:
            raise ValueError(f"Unsupported device MODEL: {fields['MODEL']}")
        return fields

    def _acquire_device_info(self):
        """Request INFO and wait at most INFO_TIMEOUT_SEC for this connection."""
        self._clear_identity("info_timeout")
        deadline = time.monotonic() + self.INFO_TIMEOUT_SEC
        try:
            with self._rx_lock:
                self.send_command("INFO")
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        self._clear_identity("info_timeout")
                        return False

                    has_timeout = hasattr(self.serial, "timeout")
                    old_timeout = getattr(self.serial, "timeout", None)
                    if has_timeout:
                        self.serial.timeout = remaining if old_timeout is None else min(float(old_timeout), remaining)
                    try:
                        raw = self.serial.readline()
                    finally:
                        if has_timeout:
                            self.serial.timeout = old_timeout

                    if not raw:
                        # pySerial normally blocks up to its configured timeout;
                        # test doubles may return immediately on an empty queue.
                        remaining = deadline - time.monotonic()
                        if remaining > 0:
                            time.sleep(min(0.01, remaining))
                        continue

                    decoded = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
                    line = decoded.strip()
                    if line.startswith("INFO"):
                        try:
                            self.device_info = self._parse_info_line(line)
                        except ValueError as exc:
                            self._clear_identity(str(exc))
                            return False
                        self._identity_confirmed = True
                        self.identity_error = None
                        return True

                    # Do not lose DATA received during the INFO handshake. It
                    # will be parsed and captured exactly once by read_measurement.
                    self._pending_rx_lines.append(decoded)
        except Exception as exc:
            self._clear_identity(f"info_read_error: {exc}")
            return False

    def connect(self):
        # A new connection must never inherit a previous device's identity or
        # unread lines, even if opening the port later fails.
        self._clear_identity("connection_not_identified")
        self._pending_rx_lines.clear()
        self.connected = False
        if serial is None:
            self.identity_error = "pyserial_unavailable"
            return False

        try:
            self.serial = serial.Serial(
                self.serial_port,
                self.baudrate,
                timeout=1,
            )
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            # Opening an Arduino Uno serial port resets the board.
            time.sleep(2.0)
            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()
            self.raw_log_collector.reset()
            self.connected = True
            print("SERIAL CONNECTED", self.serial_port, self.baudrate)
            # A missing/invalid INFO does not close the port: telemetry may
            # still be inspected, but every drive-capable command remains gated.
            self._acquire_device_info()
            return True
        except Exception as exc:
            print("SERIAL CONNECT ERROR", exc)
            self.connected = False
            self._clear_identity(f"connection_error: {exc}")
            try:
                if self.serial:
                    self.serial.close()
            except Exception:
                pass
            self.serial = None
            return False

    def _validate_command(self, command):
        if not isinstance(command, str) or not command or command.strip() != command:
            raise ValueError("Invalid motor command")
        if "\n" in command or "\r" in command:
            raise ValueError("Motor command must be a single line")
        if command in self.SIMPLE_COMMANDS:
            return command
        pwm_match = re.fullmatch(r"PWM=(0|[1-9][0-9]{0,2})", command)
        if pwm_match:
            pwm = int(pwm_match.group(1))
            if pwm <= 255:
                return command
            raise ValueError("PWM must be between 0 and 255")
        target_match = re.fullmatch(r"TARGET=([+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?)", command)
        if target_match and math.isfinite(float(target_match.group(1))):
            return command
        raise ValueError(f"Unsupported motor command: {command}")

    def forward(self):
        self.require_identified_device()
        result = self.send_command("FWD")
        self.direction = "FWD"
        return result

    def reverse(self):
        self.require_identified_device()
        result = self.send_command("REV")
        self.direction = "REV"
        return result

    def set_pwm(self, pwm):
        value = max(0, min(255, int(pwm)))
        result = self.send_command(f"PWM={value}")
        self.last_pwm = value
        return result

    def stop_breakin(self):
        first_error = None
        try:
            self.set_pwm(0)
        except Exception as exc:
            first_error = exc
        try:
            result = self.send_command("STOP")
        except Exception as exc:
            if first_error is None:
                first_error = exc
            result = None
        if first_error is not None:
            raise first_error
        return result

    def emergency_stop(self):
        first_error = None
        try:
            self.set_pwm(0)
        except Exception as exc:
            first_error = exc
        try:
            self.send_command("STOP")
        except Exception as exc:
            if first_error is None:
                first_error = exc
        try:
            self.disconnect()
        except Exception as exc:
            if first_error is None:
                first_error = exc
        if first_error is not None:
            raise first_error

    def disconnect(self):
        port = self.serial
        self.serial = None
        self.connected = False
        self._clear_identity("disconnected")
        self._pending_rx_lines.clear()
        if port:
            port.close()

    def send_command(self, command):
        command = self._validate_command(command)
        pwm_match = re.fullmatch(r"PWM=(0|[1-9][0-9]{0,2})", command)
        pwm_value = int(pwm_match.group(1)) if pwm_match else None
        allowed_unidentified = command in self.SAFE_UNIDENTIFIED_COMMANDS
        if pwm_value is not None and pwm_value == 0:
            allowed_unidentified = True
        if not self.identified and not allowed_unidentified:
            raise RuntimeError(
                f"Motor command rejected while device identity is unconfirmed: {command}"
            )
        if command == "VCTRL=ON" or command.startswith("TARGET="):
            raise ValueError(
                "Voltage feedback is owned by Python/UI; legacy VCTRL/TARGET commands are unsupported"
            )

        self.command_log.append(command)
        print("SERIAL TX:", command)
        if self.connected and self.serial:
            self.serial.write((command + "\n").encode("utf-8"))
        return command

    def read_measurement(self):
        """Read DATA frames, preserving exact DATA text and excluding INFO metadata."""
        if not (self.connected and self.serial):
            return None

        latest_data = None
        with self._rx_lock:
            while self._pending_rx_lines or self.serial.in_waiting:
                if self._pending_rx_lines:
                    decoded = self._pending_rx_lines.popleft()
                else:
                    raw = self.serial.readline()
                    decoded = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else str(raw)
                if not decoded:
                    continue
                line = decoded.strip()
                # INFO belongs to DeviceInfo registration metadata, not the
                # immutable measurement body. Legacy INFO headers already
                # stored in old RawLogs remain readable by the legacy parser.
                if line.startswith("INFO,"):
                    continue
                # Retain every non-INFO line byte-for-byte, including blank
                # lines, before applying parser-oriented filtering.
                self.raw_log_collector.append(decoded)
                if not line:
                    continue
                print("SERIAL RX:", line)
                if line.startswith("DATA,"):
                    latest_data = line

        if latest_data is None:
            return None

        self.last_raw_data = latest_data
        try:
            return self.csv_parser.parse(latest_data)
        except (ValueError, TypeError):
            return None
