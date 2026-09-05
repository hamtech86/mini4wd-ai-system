"""Break-in controller adapter for Local-first Raw Log persistence."""

from __future__ import annotations

from datetime import datetime

from raw_log_library import RawLog, RawLogLibrary

from .breakin_controller import BreakinController


class LocalRawLogBreakinController(BreakinController):
    """Persist the Serial Raw Log Collector snapshot at measurement end.

    The inherited motor control, analysis, safety, and resume behavior is not
    changed. This adapter only adds the Local Raw Log registration boundary.
    """

    def __init__(self, *args, raw_log_library=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.raw_log_library = raw_log_library or RawLogLibrary()
        self.last_raw_log_id = None
        self.last_raw_log_path = None

    def start(self, recipe, instance_id=None, resume=False):
        if hasattr(self.serial, "reset_raw_log"):
            self.serial.reset_raw_log()
        try:
            result = super().start(recipe, instance_id=instance_id, resume=resume)
        except Exception:
            self._register_raw_log()
            raise
        self._register_raw_log()
        return result

    def _register_raw_log(self):
        raw_body = getattr(self.serial, "raw_log", "") or ""
        if not raw_body:
            return None

        session_id = getattr(self.session, "session_id", None)
        firmware = getattr(self.session, "firmware_version", "") or ""
        benchmark_type = getattr(self, "benchmark_type", None) or self.active_recipe_name or ""
        baseline_pwm = getattr(self, "benchmark_baseline_pwm", None)
        purpose = getattr(self, "benchmark_purpose", None)
        notes = ""
        if baseline_pwm is not None:
            notes = f"baseline_pwm={baseline_pwm}"
        if purpose:
            notes = f"{notes}; purpose={purpose}" if notes else f"purpose={purpose}"
        record = RawLog(
            device_type="MOTOR",
            firmware_version=firmware,
            device_instance_id=self.active_instance_id,
            motor_id=self.active_instance_id,
            measurement_session_id=session_id,
            acquired_at=datetime.now().isoformat(timespec="seconds"),
            measurement_condition=benchmark_type,
            notes=notes,
        )
        path = self.raw_log_library.register(record, raw_body)
        self.last_raw_log_id = record.log_id
        self.last_raw_log_path = path
        return record
