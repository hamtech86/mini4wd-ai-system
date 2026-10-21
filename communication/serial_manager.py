"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 serial_manager.py
=====================================================

Arduinoとのシリアル通信管理
Communication層は通信のみを担当する。
"""

from PyQt5.QtCore import QObject, QThread, pyqtSignal

import time
import threading
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

                # Keep exact non-INFO serial text before parsing. INFO is an
                # auxiliary identity response and must not enter measurement RawLog.
                raw_line = self.serial_port.readline().decode("utf-8", errors="ignore")
                line = raw_line.rstrip("\r\n")
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
            if self._emergency_stop_latched:
                self.error.emit("Reconnect blocked: emergency STOP latch requires a new application session.")
                return False
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

                # Opening a USB serial port resets the Arduino. Do not expose
                # the connection as ready until the firmware boot window has
                # completed.
                time.sleep(self.ARDUINO_BOOT_SETTLE_SEC)
                self.serial.reset_input_buffer()
                self.serial.reset_output_buffer()

                self.reader = SerialReader(self.serial, self.raw_log_collector)
                self.reader.received.connect(self.received)
                self.reader.error.connect(self.error)
                self.reader.start()

                logger.success("Arduino Connected")
                self.connected.emit()
                return True

            except Exception as e:
                logger.exception(e)
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

            if errors:
                message = "Disconnect cleanup encountered errors: " + "; ".join(errors)
                logger.error(message)
                self.error.emit(message)
            else:
                logger.success("Arduino Disconnected")
            self.disconnected.emit()

    def send(self, command: str) -> bool:
        """Arduinoへコマンド送信, with a fail-closed emergency STOP latch."""
        with self._command_lock:
            normalized = str(command).strip().upper()
            drive_command = normalized in ("START", "FWD", "REV", "RESUME") or (
                normalized.startswith("PWM=") and normalized != "PWM=0"
            )
            if drive_command and self._emergency_stop_latched:
                self.error.emit("Drive command blocked: emergency STOP latch is active; new application session required.")
                logger.warning(f"TX blocked by emergency STOP latch: {command}")
                return False
            if not self.is_connected:
                self.error.emit("Serial port is not connected.")
                return False

            try:
                message = f"{command}\n"
                self.serial.write(message.encode("utf-8"))
                logger.debug(f"TX : {command}")
                return True

            except Exception as e:
                logger.exception(e)
                self.error.emit(str(e))
                return False

    def emergency_stop(self):
        """Serialize PWM=0 and STOP, then block all later drive commands."""
        outcome = {"pwm_zero": False, "stop_command": False, "disconnect": False, "errors": []}
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
                self.disconnect()
                outcome["disconnect"] = True
            except Exception as exc:
                outcome["errors"].append(f"disconnect: {type(exc).__name__}: {exc}")
        self.last_emergency_stop_result = outcome
        return outcome

    def start_breakin(self):
        return self.send(CMD_START)

    def stop_breakin(self):
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
