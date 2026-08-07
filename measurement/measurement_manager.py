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

    def _parse_frame(self, raw):
        """Convert an Arduino MOTOR_BREAKIN_V3 DATA CSV frame."""
        # Keep the Measurement contract stable even when no frame is available.
        defaults = {
            "record_type": "DATA",
            "device_model": "MOTOR_BREAKIN_V3",
            "instance_id": "UNKNOWN",
            "elapsed_time": int(time.time() * 1000),
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

        if not raw:
            return defaults

        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", errors="replace")

        fields = [field.strip() for field in str(raw).strip().split(",")]
        if len(fields) < 3 or fields[0] != "DATA":
            return defaults

        # MOTOR_BREAKIN_V3 DATA contract:
        # DATA,model,instance,elapsed,raw_acs1,raw_acs2,
        # current1,current2,voltage1,voltage2,motor_voltage,pwm,
        # direction,state,current_avg,power,current_ripple,voltage_ripple,
        # peak_power,peak_current,peak_voltage,peak_pwm,
        # brush_peak_current,raw_magnetic,magnetic_level,motor_temperature
        defaults["record_type"] = fields[0]
        defaults["device_model"] = fields[1] or "MOTOR_BREAKIN_V3"
        defaults["instance_id"] = fields[2] or "UNKNOWN"

        if len(fields) > 3:
            defaults["elapsed_time"] = self._to_int(fields[3], defaults["elapsed_time"])
        if len(fields) > 4:
            defaults["raw_acs1"] = self._to_int(fields[4])
        if len(fields) > 5:
            defaults["raw_acs2"] = self._to_int(fields[5])
        if len(fields) > 6:
            defaults["current1"] = self._to_float(fields[6])
        if len(fields) > 7:
            defaults["current2"] = self._to_float(fields[7])
        if len(fields) > 8:
            defaults["voltage1"] = self._to_float(fields[8])
        if len(fields) > 9:
            defaults["voltage2"] = self._to_float(fields[9])
        if len(fields) > 10:
            defaults["motor_voltage"] = self._to_float(fields[10])
        if len(fields) > 11:
            defaults["pwm"] = self._to_int(fields[11])
        if len(fields) > 12 and fields[12]:
            defaults["direction"] = fields[12]
        if len(fields) > 13 and fields[13]:
            defaults["state"] = fields[13]
        if len(fields) > 14:
            defaults["current_avg"] = self._to_float(fields[14])
        if len(fields) > 15:
            defaults["power"] = self._to_float(fields[15])
        if len(fields) > 16:
            defaults["current_ripple"] = self._to_float(fields[16])
        if len(fields) > 17:
            defaults["voltage_ripple"] = self._to_float(fields[17])
        if len(fields) > 18:
            defaults["peak_power"] = self._to_float(fields[18])
        if len(fields) > 19:
            defaults["peak_current"] = self._to_float(fields[19])
        if len(fields) > 20:
            defaults["peak_voltage"] = self._to_float(fields[20])
        if len(fields) > 21:
            defaults["peak_pwm"] = self._to_int(fields[21])
        if len(fields) > 22:
            defaults["brush_peak_current"] = self._to_float(fields[22])
        if len(fields) > 23:
            defaults["raw_magnetic"] = self._to_int(fields[23])
        if len(fields) > 24:
            defaults["magnetic_level"] = self._to_float(fields[24])
        if len(fields) > 25:
            defaults["motor_temperature"] = self._to_float(fields[25])

        return defaults

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
