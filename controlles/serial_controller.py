"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 serial_controller.py
=====================================================

Serial Controller

Communication層とMeasurement層を接続する。
UI・Analysis・DatabaseはこのController経由で
Measurementを受け取る。
"""

from __future__ import annotations

from typing import Callable, Optional

from communication.serial_manager import SerialManager
from communication.csv_parser import CSVParser

from measurement.measurement_manager import MeasurementManager
from measurement.measurement_session import MeasurementType


class SerialController:
    """
    Communication Controller
    """

    def __init__(self):

        self.serial = SerialManager()

        self.parser = CSVParser()

        self.measurements = MeasurementManager()

        #
        # Measurement生成後の通知先
        #

        self.on_measurement: Optional[Callable] = None

    # -------------------------------------------------
    # Serial
    # -------------------------------------------------

    def connect(
        self,
        port: str,
        baudrate: int = 57600,
    ):

        self.serial.connect(
            port=port,
            baudrate=baudrate,
        )

    def disconnect(self):

        self.serial.disconnect()

    @property
    def is_connected(self):

        return self.serial.is_connected

    # -------------------------------------------------
    # Session
    # -------------------------------------------------

    def start_session(
        self,
        measurement_type: MeasurementType = MeasurementType.BREAKIN,
    ):
        """
        Measurement Session開始
        """

        self.measurements.start_session(measurement_type)

    def finish_session(self):
        """
        Measurement Session終了
        """

        self.measurements.finish_session()

    def cancel_session(self):
        """
        Measurement Sessionキャンセル
        """

        self.measurements.cancel_session()

    # -------------------------------------------------
    # Receive
    # -------------------------------------------------

    def update(self):
        """
        1回分受信
        """

        line = self.serial.readline()

        if not line:
            return None

        data = self.parser.parse(line)

        measurement = self.measurements.create_measurement(data)

        #
        # UI通知
        #

        if self.on_measurement is not None:
            self.on_measurement(measurement)

        return measurement

    # -------------------------------------------------
    # Arduino Command
    # -------------------------------------------------

    def send(self, command: str):

        self.serial.send(command)

