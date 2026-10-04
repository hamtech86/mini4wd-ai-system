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

import math
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

    def _parse_frame(self, raw):
        """Convert one received DATA frame without fabricating missing values.

        Invalid/missing control data is rejected at the Measurement boundary.
        The SerialManager RawLog collector has already preserved the original
        serial line, so rejecting it here does not delete or alter RawLog data.
        """
        if not isinstance(raw, dict):
            return None

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

        if raw.get("record_type") != "DATA":
            return None

        # A missing field is INVALID, never an implicit 0 V / 0 A value.
        required = (
            "elapsed_time", "current1", "current2",
            "voltage1", "voltage2", "motor_voltage",
            "pwm", "direction", "state",
        )
        if any(raw.get(name) is None for name in required):
            return None

        for name in ("elapsed_time", "current1", "current2",
                     "voltage1", "voltage2", "motor_voltage", "pwm"):
            try:
                if not math.isfinite(float(raw.get(name))):
                    return None
            except (TypeError, ValueError):
                return None

        # Plausibility rejection is intentionally above the configured
        # 5 A safety limit so an actual over-current remains VALID and reaches
        # the safety mechanism instead of being hidden as an anomaly.
        if float(raw["elapsed_time"]) < 0:
            return None
        if not (0.0 <= float(raw["voltage1"]) <= 12.0 and
                0.0 <= float(raw["voltage2"]) <= 12.0 and
                0.0 <= float(raw["motor_voltage"]) <= 12.0):
            return None
        if abs(float(raw["current1"])) > 100.0 or abs(float(raw["current2"])) > 100.0:
            return None
        try:
            pwm = int(float(raw["pwm"]))
        except (TypeError, ValueError):
            return None
        if not 0 <= pwm <= 255:
            return None

        fields = raw

        # MOTOR_BREAKIN_V3 DATA contract:
        # DATA,model,instance,elapsed,raw_acs1,raw_acs2,
        # current1,current2,voltage1,voltage2,motor_voltage,pwm,
        # direction,state,current_avg,power,current_ripple,voltage_ripple,
        # peak_power,peak_current,peak_voltage,peak_pwm,
        # brush_peak_current,raw_magnetic,magnetic_level,motor_temperature
        defaults["record_type"] = fields.get("record_type")
        defaults["device_model"] = fields.get("device_model") or "MOTOR_BREAKIN_V3"
        defaults["instance_id"] = fields.get("instance_id") or "UNKNOWN"
        defaults["elapsed_time"] = self._to_int(fields.get("elapsed_time"), defaults["elapsed_time"])
        defaults["raw_acs1"] = self._to_int(fields.get("raw_acs1"))
        defaults["raw_acs2"] = self._to_int(fields.get("raw_acs2"))
        defaults["current1"] = self._to_float(fields.get("current1"))
        defaults["current2"] = self._to_float(fields.get("current2"))
        defaults["voltage1"] = self._to_float(fields.get("voltage1"))
        defaults["voltage2"] = self._to_float(fields.get("voltage2"))
        defaults["motor_voltage"] = self._to_float(fields.get("motor_voltage"))
        defaults["pwm"] = self._to_int(fields.get("pwm"))
        defaults["direction"] = fields.get("direction") or defaults["direction"]
        defaults["state"] = fields.get("state") or defaults["state"]
        for name in ("current_avg","power","current_ripple","voltage_ripple","peak_power",
                     "peak_current","peak_voltage","brush_peak_current","magnetic_level",
                     "motor_temperature"):
            if fields.get(name) is not None:
                defaults[name] = self._to_float(fields.get(name))
        for name in ("peak_pwm","raw_magnetic"):
            if fields.get(name) is not None:
                defaults[name] = self._to_int(fields.get(name))

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
