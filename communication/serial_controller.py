"""
Serial Controller Interface
MOTOR_BREAKIN_V3

Break-in Controller <-> Arduino communication layer.

Arduino firmware MOTOR_BREAKIN_V3 explicit-ARM protocol:
  ARM=<8-hex-token> -> ARMED,<same-token>
  FWD@<token>
  REV@<token>
  PWM=<0..255>@<token>
  STOP (revokes token)
"""

try:
    import serial
except ImportError:
    serial = None

import time
import re
import threading
import secrets

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
        self.device_reboot_detected = False
        self.device_reboot_reason = ""
        self.device_reboot_raw_line = None
        # Serialize every serial command with emergency STOP. Once latched,
        # drive commands remain blocked for this controller's lifetime.
        self._command_lock = threading.RLock()
        self._emergency_stop_latched = False
        self._emergency_stop_requested = threading.Event()
        self._emergency_stop_generation = 0
        self._active_arm_token = None

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
        # Serialize the complete connection lifecycle with emergency STOP.
        # A STOP that acquires this lock first permanently blocks this attempt;
        # if connect owns it first, STOP runs only after connect has completed.
        with self._ensure_command_lock():
            stop_was_already_latched = self._stop_requested()
            # A new connection attempt always invalidates any prior identity.
            self.identity_verified = False
            self.device_info = None
            self.identity_error = "INFO identity has not been verified."
            if serial is None:
                return False

            try:
                self.serial = serial.Serial(
                    self.serial_port,
                    self.baudrate,
                    timeout=1
                )
                self.serial.reset_input_buffer()
                self.serial.reset_output_buffer()
                # Opening an Arduino Uno serial port resets the board. Wait for
                # firmware startup before reporting the port as ready.
                time.sleep(2.0)
                self.serial.reset_input_buffer()
                self.serial.reset_output_buffer()
                self.raw_log_collector.reset()
                self.identity_verified = False
                self.device_info = None
                self.identity_error = "INFO response not received."
                self.connected = True
                print("SERIAL CONNECTED", self.serial_port, self.baudrate)
                self.send_command("INFO")
                # Port connectivity and device identity are separate states.
                # Keep the port available for safe STOP/PWM=0 commands, while
                # send_command() blocks drive commands until INFO is verified.
                self._verify_info_response(timeout=1.0)
                if not stop_was_already_latched and self._stop_requested():
                    self.identity_verified = False
                    self.device_info = None
                    self.identity_error = "Connection aborted by an emergency STOP racing with connect."
                    self.disconnect()
                    return False
                return True
            except Exception as e:
                print("SERIAL CONNECT ERROR", e)
                handle = self.serial
                try:
                    if handle:
                        handle.close()
                except Exception as close_exc:
                    print("SERIAL CONNECT CLEANUP ERROR", close_exc)
                finally:
                    self.serial = None
                    self.connected = False
                    self.identity_verified = False
                    self.device_info = None
                    self.identity_error = "Serial connection failed: " + str(e)
                return False

    def _verify_info_response(self, timeout=1.0):
        """Require an explicit, valid INFO response after opening the port."""
        deadline = time.monotonic() + max(0.0, float(timeout))
        while self.connected and self.serial and time.monotonic() < deadline:
            try:
                if not self.serial.in_waiting:
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
            # INFO is auxiliary identity metadata and is excluded from RawLog.
            self.raw_log_collector.append(decoded)
            if line.startswith("DATA,"):
                self.last_raw_data = line
        self.identity_verified = False
        self.device_info = None
        self.identity_error = "INFO response timed out."
        return False

    def _validate_info_record(self, info):
        """Apply semantic identity checks after strict INFO field parsing."""
        if info.get("TYPE") != "MOTOR":
            raise ValueError("Unexpected TYPE")
        if info.get("MODEL") != "MOTOR_BREAKIN_V3":
            raise ValueError("Unexpected MODEL")
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
        if result is not False:
            self.last_pwm = requested_pwm
        return result

    def stop_breakin(self):
        self.set_pwm(0)
        return self.send_command("STOP")

    def emergency_stop(self):
        """Fail closed against concurrent and subsequent drive commands.

        The lock orders in-flight writes before STOP, then the latch blocks any
        later positive-PWM/direction/restart command from this controller.
        Results describe command-path attempts, not physical motor state.
        """
        outcome = {"pwm_zero": False, "stop_command": False, "disconnect": False, "errors": []}
        # Publish the stop request before waiting for any in-flight serial operation.
        # Commands check this event under the command lock; an already-started
        # write may finish, but no later drive command may begin after the request.
        self._emergency_stop_generation = getattr(self, "_emergency_stop_generation", 0) + 1
        self._ensure_stop_event().set()
        with self._ensure_command_lock():
            self._emergency_stop_latched = True
            try:
                outcome["pwm_zero"] = self.set_pwm(0) is not False
            except Exception as exc:
                outcome["errors"].append(f"PWM=0: {type(exc).__name__}: {exc}")
            try:
                outcome["stop_command"] = self.send_command("STOP") is not False
            except Exception as exc:
                outcome["errors"].append(f"STOP: {type(exc).__name__}: {exc}")
            try:
                self.disconnect()
                outcome["disconnect"] = True
            except Exception as exc:
                outcome["errors"].append(f"disconnect: {type(exc).__name__}: {exc}")
        self.last_emergency_stop_result = outcome
        return outcome

    def _ensure_stop_event(self):
        event = getattr(self, "_emergency_stop_requested", None)
        if event is None:
            event = threading.Event()
            self._emergency_stop_requested = event
        return event

    def _stop_requested(self):
        return self._ensure_stop_event().is_set() or getattr(self, "_emergency_stop_latched", False)

    def _ensure_command_lock(self):
        # __new__ is used by isolated tests; initialize lazily there too.
        lock = getattr(self, "_command_lock", None)
        if lock is None:
            lock = threading.RLock()
            self._command_lock = lock
        return lock

    def disconnect(self):
        with self._ensure_command_lock():
            handle = self.serial
            try:
                if handle:
                    handle.close()
            finally:
                self.serial = None
                self.connected = False
                self.identity_verified = False
                self.device_info = None
                self._active_arm_token = None
                self.identity_error = "Disconnected; identity verification reset."

    def arm(self):
        """Explicitly authorize one run with a fresh token; this command never drives."""
        with self._ensure_command_lock():
            stop_generation = getattr(self, "_emergency_stop_generation", 0)
            if not (self.connected and self.serial and self.identity_verified):
                self.identity_error = "ARM blocked: connected, verified MOTOR_BREAKIN_V3 identity required."
                return False
            if getattr(self, "_active_arm_token", None) and not self._stop_requested():
                return True
            self.device_reboot_detected = False
            self.device_reboot_reason = ""
            self.device_reboot_raw_line = None
            token = secrets.token_hex(4).upper()
            result = self.send_command("ARM=" + token)
            # Firmware samples 200 ACS712 readings before ARMED; allow that bounded calibration time.
            if result is False or not self._wait_for_command_ack(expected='ARMED,' + token, timeout=2.0):
                self._active_arm_token = None
                self.identity_error = "ARM was not acknowledged by firmware; drive remains blocked."
                return False
            # A STOP request is published before it waits for this lock. If one
            # arrived during the acknowledgement wait, never erase it here.
            if getattr(self, "_emergency_stop_generation", 0) != stop_generation:
                self._active_arm_token = None
                self.identity_error = "ARM cancelled: emergency STOP arrived during ARM handshake."
                return False
            self._active_arm_token = token
            # Measurement capture starts after ARM, immediately before the first
            # tagged drive command; discard idle DATA collected during handshake.
            self.raw_log_collector.reset()
            # Only this explicit user/workflow call may clear the host-side STOP latch.
            self._emergency_stop_latched = False
            self._ensure_stop_event().clear()
            self.identity_error = ""
            return True

    def _wait_for_command_ack(self, expected, timeout=1.0):
        """Wait for this exact ARM token acknowledgement, not a stale generic OK."""
        deadline = time.monotonic() + max(0.0, float(timeout))
        while self.connected and self.serial and time.monotonic() < deadline:
            try:
                if not self.serial.in_waiting:
                    time.sleep(0.01)
                    continue
                original_timeout = getattr(self.serial, "timeout", None)
                try:
                    self.serial.timeout = max(0.0, deadline - time.monotonic())
                    decoded = self.serial.readline().decode("utf-8", errors="replace")
                finally:
                    self.serial.timeout = original_timeout
            except Exception as exc:
                self.identity_error = "Command acknowledgement read failed: " + str(exc)
                return False
            line = decoded.strip()
            if line == expected:
                return True
            if line.startswith("ERROR,"):
                self.identity_error = line
                return False
            # Generic OK or an acknowledgement for an older token is stale;
            # it cannot authorize this ARM attempt.
            if line == "OK" or line.startswith("ARMED,"):
                continue
            if line.startswith("INFO"):
                try:
                    self._validate_info_record(self.parser.parse(line))
                except (ValueError, KeyError):
                    self.identity_verified = False
                    self.device_info = None
            # Ignore unrelated telemetry during the ARM handshake; the
            # measurement RawLog is reset after the exact token acknowledgement.
        return False

    def send_command(self, command):
        with self._ensure_command_lock():
            self.command_log.append(command)
            print("SERIAL TX:", command)
            normalized = str(command).strip().upper()
            drive_command = normalized in ("START", "FWD", "REV", "RESUME") or (
                normalized.startswith("PWM=") and normalized != "PWM=0"
            )
            is_arm = normalized.startswith("ARM=")
            if drive_command and (self._stop_requested() or not getattr(self, '_active_arm_token', None)):
                self.identity_error = "Drive command blocked: explicit ARM is required after STOP and before each run."
                print("SERIAL TX BLOCKED:", command, self.identity_error)
                return False
            if (drive_command or is_arm) and not self.identity_verified:
                self.identity_error = "Drive/ARM command blocked: INFO identity is not verified."
                print("SERIAL TX BLOCKED:", command, self.identity_error)
                return False
            if self.connected and self.serial:
                wire_command = str(command)
                if drive_command:
                    wire_command = wire_command + "@" + getattr(self, "_active_arm_token")
                self.serial.write((wire_command + "\n").encode("utf-8"))
                if normalized == "STOP":
                    self._active_arm_token = None
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
            line = decoded.strip()
            if not line.startswith("INFO"):
                self.raw_log_collector.append(decoded)
            if not line:
                continue
            print("SERIAL RX:", line)
            if line.startswith("INFO"):
                # INFO is expected at connect/ARM, but during an armed run it
                # indicates that firmware restarted and lost its ARM state.
                if getattr(self, "_active_arm_token", None) and not self._stop_requested():
                    self.device_reboot_detected = True
                    self.device_reboot_reason = "Unexpected INFO received during an armed run; firmware reboot suspected."
                    self.device_reboot_raw_line = line
                    self.identity_verified = False
                    self.device_info = None
                    self.identity_error = self.device_reboot_reason
                    self._active_arm_token = None
                    continue
                # Outside an active armed run, INFO is ordinary identity metadata.
                try:
                    info = self.parser.parse(line)
                    self._validate_info_record(info)
                except (ValueError, KeyError):
                    self.identity_verified = False
                    self.device_info = None
                    self.identity_error = "Invalid INFO identity."
                continue
            if line.startswith("DATA,"):
                latest_data = line

        if latest_data is not None:
            self.last_raw_data = latest_data

        return latest_data
