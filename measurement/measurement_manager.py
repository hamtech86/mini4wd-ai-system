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
from communication.csv_parser import CSVParser


class MeasurementManager:
    """Measurement Manager"""

    def __init__(self, serial_controller=None):
        self.serial_controller = serial_controller
        self.session: Optional[MeasurementSession] = None
        self.logger = MeasurementLogger()
        self.filters = FilterGroup()
        self.last_measurement: Optional[Measurement] = None
        self.last_rejection_reason = None

    NON_RUNNING_FRAME_WAIT_SEC = 0.25
    NON_RUNNING_POLL_SEC = 0.01

    def collect(self):
        """
        BreakinController interface.
        Arduino frame acquisition entry point.

        READY/INIT telemetry is expected while the firmware transitions into
        RUN. Wait briefly for a RUN frame rather than counting startup telemetry
        as a failed control sample. The wait is bounded; absent RUN telemetry
        still returns None and remains subject to the controller's safety limit.
        """
        deadline = None
        self.last_rejection_reason = None
        parser = getattr(self.serial_controller, "parser", None) or CSVParser()

        while True:
            raw = None
            if self.serial_controller:
                raw = self.serial_controller.read_measurement()

            if isinstance(raw, str):
                # SerialController returns the exact DATA CSV line. Parse it using
                # the canonical 26-column protocol parser before validation.
                try:
                    raw = parser.parse(raw)
                except (TypeError, ValueError, OverflowError) as exc:
                    self.last_rejection_reason = f"DATA parse failed: {type(exc).__name__}: {exc}"
                    self.last_measurement = None
                    return None

            data = self._parse_frame(raw)
            if data is not None:
                self.last_rejection_reason = None
                return self.create_measurement(data)
            self.last_rejection_reason = self._explain_rejected_frame(raw)

            is_non_running_data = (
                isinstance(raw, dict)
                and raw.get("record_type") == "DATA"
                and isinstance(raw.get("state"), str)
                and raw["state"].strip().upper() not in ("RUN", "RUNNING")
            )
            if not is_non_running_data:
                # After observing startup telemetry, an empty serial poll is
                # expected while waiting for the next 100 ms DATA frame. Keep
                # waiting only inside that already-started bounded window.
                if deadline is not None and raw is None and time.monotonic() < deadline:
                    time.sleep(self.NON_RUNNING_POLL_SEC)
                    continue
                # Never reuse a previous valid sample after a missing/rejected frame.
                self.last_measurement = None
                return None

            if deadline is None:
                deadline = time.monotonic() + self.NON_RUNNING_FRAME_WAIT_SEC
            if time.monotonic() >= deadline:
                self.last_measurement = None
                return None
            time.sleep(self.NON_RUNNING_POLL_SEC)


    @staticmethod
    def _explain_rejected_frame(raw):
        """Return a concise diagnostic without changing acceptance rules."""
        if raw is None:
            return "no DATA frame received"
        if not isinstance(raw, dict):
            return f"unexpected frame type: {type(raw).__name__}"
        if raw.get("record_type") != "DATA":
            return f"unexpected record_type: {raw.get('record_type')!r}"
        required = (
            "device_model", "instance_id", "elapsed_time", "raw_acs1", "raw_acs2",
            "current1", "current2", "voltage1", "voltage2", "motor_voltage",
            "pwm", "direction", "state", "current_avg", "power",
            "current_ripple", "voltage_ripple", "peak_power", "peak_current",
            "peak_voltage", "peak_pwm", "brush_peak_current", "raw_magnetic",
            "magnetic_level", "motor_temperature",
        )
        missing = [name for name in required if raw.get(name) is None]
        if missing:
            return "missing DATA fields: " + ",".join(missing)
        if str(raw.get("state", "")).strip().upper() not in ("RUN", "RUNNING"):
            return f"DATA state not running: {raw.get('state')!r}"
        if raw.get("device_model") != "MOTOR_BREAKIN_V3":
            return f"unexpected device_model: {raw.get('device_model')!r}"
        if raw.get("direction") not in ("FWD", "REV"):
            return f"invalid direction: {raw.get('direction')!r}"
        for name in (
            "elapsed_time", "raw_acs1", "raw_acs2", "current1", "current2",
            "voltage1", "voltage2", "motor_voltage", "pwm", "current_avg",
            "power", "current_ripple", "voltage_ripple", "peak_power",
            "peak_current", "peak_voltage", "peak_pwm", "brush_peak_current",
            "raw_magnetic", "magnetic_level", "motor_temperature",
        ):
            try:
                if not math.isfinite(float(raw.get(name))):
                    return f"non-finite numeric field: {name}={raw.get(name)!r}"
            except (TypeError, ValueError, OverflowError):
                return f"non-numeric field: {name}={raw.get(name)!r}"
        return "DATA rejected by remaining validation (integer/range/identity fields)"

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
            "device_model", "instance_id", "elapsed_time", "raw_acs1", "raw_acs2",
            "current1", "current2", "voltage1", "voltage2", "motor_voltage",
            "pwm", "direction", "state", "current_avg", "power",
            "current_ripple", "voltage_ripple", "peak_power", "peak_current",
            "peak_voltage", "peak_pwm", "brush_peak_current", "raw_magnetic",
            "magnetic_level", "motor_temperature",
        )
        if any(raw.get(name) is None for name in required):
            return None
        if not isinstance(raw.get("device_model"), str) or not raw["device_model"].strip():
            return None
        if not isinstance(raw.get("direction"), str) or not raw["direction"].strip():
            return None
        if not isinstance(raw.get("state"), str) or not raw["state"].strip():
            return None
        instance_id = raw.get("instance_id")
        if isinstance(instance_id, str):
            if not instance_id.strip():
                return None
        elif not isinstance(instance_id, int) or isinstance(instance_id, bool) or instance_id < 0:
            return None
        if raw["device_model"] != "MOTOR_BREAKIN_V3" or raw["direction"] not in ("FWD", "REV"):
            return None

        # Only telemetry emitted while the firmware is actively running may
        # drive voltage-control decisions. READY frames commonly contain 0 V
        # before the first RUN sample and must not be interpreted as failed
        # input-voltage feedback. Preserve every original frame in RawLog;
        # this filter applies only to the control/measurement path.
        if str(raw["state"]).strip().upper() not in ("RUN", "RUNNING"):
            return None

        numeric_fields = (
            "elapsed_time", "raw_acs1", "raw_acs2", "current1", "current2",
            "voltage1", "voltage2", "motor_voltage", "pwm", "current_avg",
            "power", "current_ripple", "voltage_ripple", "peak_power",
            "peak_current", "peak_voltage", "peak_pwm", "brush_peak_current",
            "raw_magnetic", "magnetic_level", "motor_temperature",
        )
        for name in numeric_fields:
            try:
                if not math.isfinite(float(raw.get(name))):
                    return None
            except (TypeError, ValueError, OverflowError):
                return None
        integer_fields = ("elapsed_time", "raw_acs1", "raw_acs2", "pwm", "peak_pwm", "raw_magnetic")
        for name in integer_fields:
            try:
                if not float(raw[name]).is_integer():
                    return None
            except (TypeError, ValueError, OverflowError):
                return None

        # Plausibility rejection is intentionally above the configured
        # 5 A safety limit so an actual over-current remains VALID and reaches
        # the safety mechanism instead of being hidden as an anomaly.
        if float(raw["elapsed_time"]) < 0:
            return None
        if not (0 <= int(raw["raw_acs1"]) <= 1023 and 0 <= int(raw["raw_acs2"]) <= 1023):
            return None
        if not (0.0 <= float(raw["voltage1"]) <= 12.0 and
                0.0 <= float(raw["voltage2"]) <= 12.0 and
                -12.0 <= float(raw["motor_voltage"]) <= 12.0):
            return None
        if abs(float(raw["current1"])) > 100.0 or abs(float(raw["current2"])) > 100.0:
            return None
        try:
            pwm = int(float(raw["pwm"]))
            peak_pwm = int(float(raw["peak_pwm"]))
        except (TypeError, ValueError, OverflowError):
            return None
        if not 0 <= pwm <= 255 or not 0 <= peak_pwm <= 255:
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
