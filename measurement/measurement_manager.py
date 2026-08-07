"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 measurement_manager.py
=====================================================

Measurement Manager

Measurement層の中核クラス。
"""

from __future__ import annotations

import time
from typing import Dict, Optional

from measurement.measurement import Measurement
from measurement.measurement_logger import MeasurementLogger
from measurement.measurement_session import (
    MeasurementSession,
    MeasurementType,
)
from measurement.filters import FilterGroup


class MeasurementManager:
    """Measurement Manager"""

    def __init__(self, serial_controller=None):
        self.serial_controller = serial_controller
        self.session: Optional[MeasurementSession] = None
        self.logger = MeasurementLogger()
        self.filters = FilterGroup()
        self.last_measurement: Optional[Measurement] = None

    def collect(self):
        """
        BreakinController interface.
        Arduino frame acquisition entry point.
        """
        raw = None

        if self.serial_controller:
            raw = self.serial_controller.read_measurement()

        data = self._parse_frame(raw)

        return self.create_measurement(data)

    def _parse_frame(self, raw):
        """Convert Arduino CSV frame to Measurement dictionary."""
        now = int(time.time() * 1000)

        return {
            "record_type": "DATA",
            "device_model": "MOTOR_BREAKIN_V3",
            "instance_id": "UNKNOWN",
            "elapsed_time": now,
            "raw_acs1": 0,
            "raw_acs2": 0,
            "current1": 0.0,
            "current2": 0.0,
            "voltage1": 0.0,
            "voltage2": 0.0,
            "motor_voltage": 0.0,
            "pwm": getattr(self.serial_controller, "last_pwm", 0),
            "direction": getattr(self.serial_controller, "direction", "FWD"),
            "state": "RUNNING",
            "current_avg": 0.0,
            "power": 0.0,
            "current_ripple": 0.0,
            "voltage_ripple": 0.0,
            "peak_power": 0.0,
            "peak_current": 0.0,
            "peak_voltage": 0.0,
            "peak_pwm": 0,
            "brush_peak_current": 0.0,
            "raw_magnetic": 0,
            "magnetic_level": 0.0,
            "motor_temperature": 0.0,
        }

    def start_session(self, measurement_type=MeasurementType.BREAKIN):
        self.session = MeasurementSession(measurement_type=measurement_type)
        self.session.start()
        self.logger.start(self.session.session_id)
        self.filters.reset()

    def finish_session(self):
        if self.session:
            self.session.finish()
            self.logger.stop()

    def cancel_session(self):
        if self.session:
            self.session.cancel()
            self.logger.stop()

    def create_measurement(self, data: Dict):
        measurement = Measurement(**data)

        if self.session:
            measurement.session_id = self.session.session_id
            self.session.add_measurement()

        self.last_measurement = measurement
        self.logger.write(measurement)

        return measurement

    @property
    def is_running(self):
        return self.session is not None and self.session.is_running

    @property
    def filtered_current(self):
        return self.filters.current.value

    @property
    def filtered_voltage(self):
        return self.filters.voltage.value

    @property
    def filtered_power(self):
        return self.filters.power.value
