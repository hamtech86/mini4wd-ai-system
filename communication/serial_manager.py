"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 serial_manager.py
=====================================================

Arduinoとのシリアル通信管理
Communication層は通信のみを担当する。
"""

from PyQt5.QtCore import QObject, QThread, pyqtSignal, Qt

import time
import threading
import secrets
import serial
import serial.tools.list_ports

from loguru import logger

from app.config import (
    DEFAULT_BAUDRATE,
    SERIAL_TIMEOUT,
)

from app.constants import (
    CMD_START,
    CMD_STOP,
    CMD_FORWARD,
    CMD_REVERSE,
    CMD_PWM,
)

from communication.csv_parser import CSVParser
from communication.raw_log_collector import RawLogCollector


class SerialReader(QThread):
    """シリアル受信スレッド"""

    received = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, serial_port, raw_log_collector=None):
        super().__init__()
        self.serial_port = serial_port
        self.parser = CSVParser()
        self.raw_log_collector = raw_log_collector
        self.running = True

    def stop(self):
        """受信停止"""
        self.running = False

    def run(self):
        while self.running:
            try:
                if not self.serial_port.is_open:
                    break

                if self.serial_port.in_waiting == 0:
                    self.msleep(5)
                    continue

                raw_line = self.serial_port.readline().decode("utf-8", errors="ignore")
                line = raw_line.rstrip("\r\n")

                # Command responses are control-plane messages, not measurement RawLog.
                if line == "OK" or line.startswith("ERROR,"):
                    self.received.emit({"record_type": "COMMAND_RESPONSE", "value": line})
                    continue

                # Keep exact non-INFO serial text before parsing.
                if self.raw_log_collector is not None and not line.startswith("INFO"):
                    self.raw_log_collector.append(raw_line)

                # CSVParser keeps DATA at its fixed 26-field contract.
                if not line:
                    continue

                data = self.parser.parse(line)
                self.received.emit(data)

            except Exception as e:
                logger.exception(e)
                self.error.emit(str(e))
                self.msleep(100)


class SerialManager(QObject):
    """Arduino通信管理.

    Opening an Arduino Uno serial port normally toggles DTR and resets the
    board.  The port can therefore be open before the firmware is ready to
    accept the first command.  Keep the connection API synchronous and make
    the controller report CONNECTED only after the boot/reset window has
    settled.
    """

    ARDUINO_BOOT_SETTLE_SEC = 2.0

    connected = pyqtSignal()
    disconnected = pyqtSignal()
    received = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.serial = None
        self.reader = None
        self.raw_log_collector = RawLogCollector()
        # All writes and emergency STOP are serialized. The latch remains
        # set for this manager instance; reconnecting cannot re-arm the motor.
        self._command_lock = threading.RLock()
        self._emergency_stop_latched = False
        self._emergency_stop_requested = threading.Event()
        self._active_arm_token = None
        self._identity_verified = False
        self.device_info = None
        self.identity_error = "INFO identity has not been verified."
        self._arm_response_event = threading.Event()
        self._arm_response_status = None

    @property
    def is_connected(self):
        return self.serial is not None and self.serial.is_open

    @property
    def raw_log(self):
        """Current measurement/connection raw-log snapshot."""
        return self.raw_log_collector.snapshot()

    @property
    def has_raw_log(self):
        return self.raw_log_collector.has_data

    def reset_raw_log(self):
        """Start a fresh raw-log capture without reconnecting the port."""
        self.raw_log_collector.reset()

    @staticmethod
    def available_ports():
        return [port.device for port in serial.tools.list_ports.comports()]

    def connect(self, port):
        with self._command_lock:
            stop_was_already_latched = self._stop_requested()
            try:
                logger.info(f"Connecting : {port}")

                self.serial = serial.Serial(
                    port=port,
                    baudrate=DEFAULT_BAUDRATE,
                    timeout=SERIAL_TIMEOUT,
                )

                self.serial.reset_input_buffer()
                self.serial.reset_output_buffer()
                self.raw_log_collector.reset()
                self._identity_verified = False
                self.device_info = None
                self.identity_error = "INFO identity has not been verified."
                self._active_arm_token = None

                # Opening a USB serial port resets the Arduino. Do not expose
                # the connection as ready until the firmware boot window has
                # completed.
                time.sleep(self.ARDUINO_BOOT_SETTLE_SEC)
                self.serial.reset_input_buffer()
                self.serial.reset_output_buffer()
                if not stop_was_already_latched and self._stop_requested():
                    raise RuntimeError("Connection aborted by an emergency STOP racing with connect.")

                self.reader = SerialReader(self.serial, self.raw_log_collector)
                self.reader.received.connect(self._observe_identity, type=Qt.DirectConnection)
                self.reader.received.connect(self.received)
                self.reader.error.connect(self.error)
                self.reader.start()
                # Request identity after the reader is live; boot INFO may have
                # been discarded during the Arduino reset/settle window.
                self.send("INFO")
                identity_deadline = time.monotonic() + 1.0
                while not self._identity_verified and time.monotonic() < identity_deadline:
                    time.sleep(0.01)

                logger.success("Arduino Connected")
                self.connected.emit()
                if not self._identity_verified:
                    self.error.emit("MOTOR_BREAKIN_V3 INFO identity was not verified; drive remains blocked.")
                return True

            except Exception as e:
                logger.exception(e)
                handle = self.serial
                try:
                    if handle is not None and getattr(handle, "is_open", False):
                        handle.close()
                except Exception as close_exc:
                    logger.exception(close_exc)
                    self.error.emit(f"Connection cleanup failed: {type(close_exc).__name__}: {close_exc}")
                finally:
                    self.serial = None
                    self.reader = None
                self.error.emit(str(e))
                return False

    def disconnect(self):
        with self._command_lock:
            errors = []
            logger.info("Disconnecting...")

            # Always clear local references/state even if a worker wait or serial
            # close raises. A failed close is reported; it is not proof the
            # physical device is disconnected.
            reader = self.reader
            handle = self.serial
            try:
                if reader is not None:
                    try:
                        reader.stop()
                        reader.wait(1000)
                    except Exception as exc:
                        errors.append(f"reader shutdown: {type(exc).__name__}: {exc}")
            finally:
                self.reader = None

            try:
                if handle is not None and getattr(handle, "is_open", False):
                    handle.close()
            except Exception as exc:
                errors.append(f"serial close: {type(exc).__name__}: {exc}")
            finally:
                self.serial = None
                self._identity_verified = False
                self.device_info = None
                self._active_arm_token = None
                self.identity_error = "Disconnected; identity verification reset."

            if errors:
                message = "Disconnect cleanup encountered errors: " + "; ".join(errors)
                logger.error(message)
                self.error.emit(message)
                self.disconnected.emit()
                return False

            logger.success("Arduino Disconnected")
            self.disconnected.emit()
            return True

    def _stop_requested(self):
        return self._emergency_stop_requested.is_set() or self._emergency_stop_latched

    def _observe_identity(self, data):
        if not isinstance(data, dict):
            return
        if data.get("record_type") == "COMMAND_RESPONSE":
            value = data.get("value")
            self._arm_response_status = value == "OK"
            self._arm_response_event.set()
            return
        if data.get("record_type") != "INFO":
            return
        self._identity_verified = (
            data.get("TYPE") == "MOTOR"
            and data.get("MODEL") == "MOTOR_BREAKIN_V3"
            and all(isinstance(data.get(key), str) and data.get(key).strip()
                    for key in ("FW", "BUILD", "ID"))
        )
        if self._identity_verified:
            self.device_info = {key: data[key] for key in ("TYPE", "MODEL", "FW", "BUILD", "ID")}
            self.identity_error = ""
        else:
            self.device_info = None
            self.identity_error = "Unexpected or incomplete MOTOR_BREAKIN_V3 INFO identity."

    def arm(self) -> bool:
        """Explicitly authorize one run with a fresh, non-driving token."""
        with self._command_lock:
            if not self.is_connected or not self._identity_verified:
                self.error.emit("ARM blocked: verified MOTOR_BREAKIN_V3 identity required.")
                return False
            if self._active_arm_token and not self._stop_requested():
                return True
            token = secrets.token_hex(4).upper()
            self._arm_response_status = None
            self._arm_response_event.clear()
            if not self.send("ARM=" + token):
                self._active_arm_token = None
                return False
            if not self._arm_response_event.wait(timeout=1.0) or self._arm_response_status is not True:
                self._active_arm_token = None
                self.error.emit("ARM was not acknowledged by firmware; drive remains blocked.")
                return False
            self._active_arm_token = token
            # Only this explicit operation clears the host STOP latch.
            self._emergency_stop_latched = False
            self._emergency_stop_requested.clear()
            return True

    def send(self, command: str) -> bool:
        """Send safe commands normally; drive commands require explicit ARM."""
        with self._command_lock:
            normalized = str(command).strip().upper()
            drive_command = normalized in ("START", "FWD", "REV", "RESUME") or (
                normalized.startswith("PWM=") and normalized != "PWM=0"
            )
            is_arm = normalized.startswith("ARM=")
            if drive_command and (self._stop_requested() or not self._active_arm_token):
                self.error.emit("Drive command blocked: explicit ARM is required before every run.")
                logger.warning(f"TX blocked until explicit ARM: {command}")
                return False
            if (drive_command or is_arm) and not self._identity_verified:
                self.error.emit("Drive/ARM blocked: INFO identity is not verified.")
                return False
            if not self.is_connected:
                self.error.emit("Serial port is not connected.")
                return False

            try:
                wire_command = str(command)
                if drive_command:
                    wire_command += "@" + self._active_arm_token
                self.serial.write((wire_command + "\n").encode("utf-8"))
                logger.debug(f"TX : {wire_command}")
                if normalized == "STOP":
                    self._active_arm_token = None
                return True
            except Exception as e:
                logger.exception(e)
                self.error.emit(str(e))
                return False

    def emergency_stop(self):
        """Serialize PWM=0 and STOP, then block all later drive commands."""
        outcome = {"pwm_zero": False, "stop_command": False, "disconnect": False, "errors": []}
        # Signal immediately; do not wait for connect/INFO or an in-flight write
        # before blocking new drive commands.
        self._emergency_stop_requested.set()
        with self._command_lock:
            self._emergency_stop_latched = True
            try:
                outcome["pwm_zero"] = self.send(f"{CMD_PWM}0")
            except Exception as exc:
                outcome["errors"].append(f"PWM=0: {type(exc).__name__}: {exc}")
            try:
                outcome["stop_command"] = self.send(CMD_STOP)
            except Exception as exc:
                outcome["errors"].append(f"STOP: {type(exc).__name__}: {exc}")
            try:
                outcome["disconnect"] = self.disconnect() is not False
                if not outcome["disconnect"]:
                    outcome["errors"].append("disconnect: serial/reader cleanup reported an error")
            except Exception as exc:
                outcome["errors"].append(f"disconnect: {type(exc).__name__}: {exc}")
        self.last_emergency_stop_result = outcome
        return outcome

    def start_breakin(self):
        return self.send(CMD_START)

    def stop_breakin(self):
        # Keep the two-step stop contract for both routine and emergency exits.
        self.send("PWM=0")
        return self.send(CMD_STOP)

    def forward(self):
        """Firmware 3.00: FWD starts forward RUN state."""
        return self.send(CMD_FORWARD)

    def reverse(self):
        """Firmware 3.00: REV starts reverse RUN state."""
        return self.send(CMD_REVERSE)

    def set_pwm(self, pwm: int):
        """Firmware 3.00: PWM=<0..255>."""
        pwm = max(0, min(255, int(pwm)))
        return self.send(f"{CMD_PWM}{pwm}")
