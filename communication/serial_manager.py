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


class SerialReader(QThread):
    """シリアル受信スレッド"""

    received = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, serial_port):
        super().__init__()
        self.serial_port = serial_port
        self.parser = CSVParser()
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

                line = (
                    self.serial_port
                    .readline()
                    .decode("utf-8", errors="ignore")
                    .strip()
                )

                if not line:
                    continue

                data = self.parser.parse(line)
                self.received.emit(data)

            except Exception as e:
                logger.exception(e)
                self.error.emit(str(e))
                self.msleep(100)


class SerialManager(QObject):
    """Arduino通信管理"""

    connected = pyqtSignal()
    disconnected = pyqtSignal()
    received = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.serial = None
        self.reader = None

    @property
    def is_connected(self):
        return self.serial is not None and self.serial.is_open

    @staticmethod
    def available_ports():
        return [port.device for port in serial.tools.list_ports.comports()]

    def connect(self, port):
        try:
            logger.info(f"Connecting : {port}")

            self.serial = serial.Serial(
                port=port,
                baudrate=DEFAULT_BAUDRATE,
                timeout=SERIAL_TIMEOUT,
            )

            self.serial.reset_input_buffer()
            self.serial.reset_output_buffer()

            self.reader = SerialReader(self.serial)
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
        try:
            logger.info("Disconnecting...")

            if self.reader is not None:
                self.reader.stop()
                self.reader.wait(1000)
                self.reader = None

            if self.serial is not None:
                if self.serial.is_open:
                    self.serial.close()
                self.serial = None

            logger.success("Arduino Disconnected")
            self.disconnected.emit()

        except Exception as e:
            logger.exception(e)
            self.error.emit(str(e))

    def send(self, command: str) -> bool:
        """Arduinoへコマンド送信"""
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
