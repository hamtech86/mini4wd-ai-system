"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 measurement/measurement_manager.py
=====================================================
Measurement Manager
"""

from __future__ import annotations

from typing import Dict, Optional

from measurement.measurement import Measurement
from measurement.measurement_logger import MeasurementLogger
from measurement.measurement_session import MeasurementSession, MeasurementType
from measurement.filters import FilterGroup


class MeasurementManager:
    """Measurement layer and MOTOR_BREAKIN_V3 frame decoder."""

    def __init__(self, serial_controller=None):
        self.serial_controller = serial_controller
        self.session: Optional[MeasurementSession] = None
        self.logger = MeasurementLogger()
        self.filters = FilterGroup()
        self.last_measurement: Optional[Measurement] = None

    def collect(self):
        raw = None
        if self.serial_controller:
            raw = self.serial_controller.read_measurement()
        data = self._parse_frame(raw)
        if data is None:
            return None
        return self.create_measurement(data)

    @staticmethod
    def _to_int(value, default=0):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _to_float(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @classmethod
    def _magnitude(cls, value, default=0.0):
        return abs(cls._to_float(value, default))

    def _parse_frame(self, raw):
        """Decode the fixed 26-field MOTOR_BREAKIN_V3 DATA frame.

        Direction is retained separately. Electrical quantities used for
        formal analysis are stored as magnitudes, so H-bridge polarity cannot
        create negative voltage/current/RPM/torque results downstream.
        """
        if not raw:
            return None
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")

        fields = [field.strip() for field in str(raw).strip().split(",")]
        if len(fields) < 3 or fields[0] != "DATA":
            return None

        data = {
            "record_type": fields[0],
            "device_model": fields[1] or "MOTOR_BREAKIN_V3",
            "instance_id": fields[2],
            "elapsed_time": self._to_int(fields[3]) if len(fields) > 3 else 0,
            "raw_acs1": self._to_int(fields[4]) if len(fields) > 4 else 0,
            "raw_acs2": self._to_int(fields[5]) if len(fields) > 5 else 0,
            "current1": self._magnitude(fields[6]) if len(fields) > 6 else 0.0,
            "current2": self._magnitude(fields[7]) if len(fields) > 7 else 0.0,
            "voltage1": self._magnitude(fields[8]) if len(fields) > 8 else 0.0,
            "voltage2": self._magnitude(fields[9]) if len(fields) > 9 else 0.0,
            "motor_voltage": self._magnitude(fields[10]) if len(fields) > 10 else 0.0,
            "pwm": self._to_int(fields[11]) if len(fields) > 11 else 0,
            "direction": fields[12] if len(fields) > 12 and fields[12] else "FWD",
            "state": fields[13] if len(fields) > 13 and fields[13] else "RUN",
            "current_avg": self._magnitude(fields[14]) if len(fields) > 14 else 0.0,
            "power": self._magnitude(fields[15]) if len(fields) > 15 else 0.0,
            "current_ripple": self._magnitude(fields[16]) if len(fields) > 16 else 0.0,
            "voltage_ripple": self._magnitude(fields[17]) if len(fields) > 17 else 0.0,
            "peak_power": self._magnitude(fields[18]) if len(fields) > 18 else 0.0,
            "peak_current": self._magnitude(fields[19]) if len(fields) > 19 else 0.0,
            "peak_voltage": self._magnitude(fields[20]) if len(fields) > 20 else 0.0,
            "peak_pwm": self._to_int(fields[21]) if len(fields) > 21 else 0,
            "brush_peak_current": self._magnitude(fields[22]) if len(fields) > 22 else 0.0,
            "raw_magnetic": self._to_int(fields[23]) if len(fields) > 23 else 0,
            "magnetic_level": self._magnitude(fields[24]) if len(fields) > 24 else 0.0,
            "motor_temperature": self._to_float(fields[25]) if len(fields) > 25 else 0.0,
        }

        if not data["instance_id"] or data["instance_id"].upper() == "UNKNOWN":
            return None
        return data

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
