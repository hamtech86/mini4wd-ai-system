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
    """Communication Controller used by the MOTOR_BREAKIN_V3 runtime."""

    def __init__(self):
        self.serial = SerialManager()
        self.parser = CSVParser()
        self.measurements = MeasurementManager()

        # BreakinController consumes the most recent DATA frame through
        # read_measurement(). SerialManager already owns the reader thread.
        self._latest_measurement = None
        self.serial.received.connect(self._on_serial_data)

        # Measurement生成後の通知先
        self.on_measurement: Optional[Callable] = None

    # -------------------------------------------------
    # Serial
    # -------------------------------------------------

    def connect(self, port: str, baudrate: int = 57600):
        # SerialManager currently owns the configured baud rate. Keep the
        # public baudrate argument for compatibility with the application API.
        return self.serial.connect(port=port)

    def disconnect(self):
        return self.serial.disconnect()

    @property
    def is_connected(self):
        return self.serial.is_connected

    @property
    def connected(self):
        """Compatibility alias used by the operator UI."""
        return self.serial.is_connected

    @property
    def raw_log(self):
        """Current measurement/connection raw-log snapshot."""
        return self.serial.raw_log

    @property
    def has_raw_log(self):
        return self.serial.has_raw_log

    def reset_raw_log(self):
        """Start a fresh raw-log capture without reconnecting the port."""
        return self.serial.reset_raw_log()

    @property
    def direction(self):
        return getattr(self, "_direction", "FWD")

    @property
    def last_pwm(self):
        return getattr(self, "_last_pwm", 0)

    def _on_serial_data(self, data):
        """Receive parsed SerialManager frames without consuming the port."""
        if not isinstance(data, dict):
            return
        if self.parser.is_data_record(data):
            self._latest_measurement = data
            self._direction = data.get("direction") or self.direction
            try:
                self._last_pwm = int(data.get("pwm", self.last_pwm) or 0)
            except (TypeError, ValueError):
                pass

    def read_measurement(self):
        """Return one newly received DATA frame for MeasurementManager."""
        data = self._latest_measurement
        self._latest_measurement = None
        return data

    # -------------------------------------------------
    # Session
    # -------------------------------------------------

    def start_session(
        self,
        measurement_type: MeasurementType = MeasurementType.BREAKIN,
    ):
        self.measurements.start_session(measurement_type)

    def finish_session(self):
        self.measurements.finish_session()

    def cancel_session(self):
        self.measurements.cancel_session()

    # -------------------------------------------------
    # Receive compatibility API
    # -------------------------------------------------

    def update(self):
        """Consume one DATA frame already received by SerialManager."""
        data = self.read_measurement()
        if not data:
            return None

        measurement = self.measurements.create_measurement(data)
        if self.on_measurement is not None:
            self.on_measurement(measurement)
        return measurement

    # -------------------------------------------------
    # Arduino Command / BreakinController adapter
    # -------------------------------------------------

    def send(self, command: str):
        return self.serial.send(command)

    def start_breakin(self):
        return self.serial.start_breakin()

    def stop_breakin(self):
        return self.serial.stop_breakin()

    def emergency_stop(self):
        return self.stop_breakin()

    def forward(self):
        self._direction = "FWD"
        return self.serial.forward()

    def reverse(self):
        self._direction = "REV"
        return self.serial.reverse()

    def set_pwm(self, pwm: int):
        pwm = max(0, min(255, int(pwm)))
        self._last_pwm = pwm
        return self.serial.set_pwm(pwm)
