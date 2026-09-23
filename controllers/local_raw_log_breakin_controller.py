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
        self._registered_raw_log_ids = []

    def start(self, recipe, instance_id=None, resume=False):
        if hasattr(self.serial, "reset_raw_log"):
            self.serial.reset_raw_log()
        self._measurement_raw_log_parts = []
        self._registered_raw_log_ids = []
        self.last_raw_log_id = None
        self.last_raw_log_path = None
        try:
            result = super().start(recipe, instance_id=instance_id, resume=resume)
        except Exception:
            # Preserve the completed/raw capture even when the inherited
            # controller reports a failure. Finalization is idempotent.
            self.finalize_benchmark_raw_log()
            raise
        self.finalize_benchmark_raw_log()
        return result

    def _freeze_measurement_raw_log(self):
        """Freeze the phase log only; persistence is finalized once per benchmark."""
        super()._freeze_measurement_raw_log()

    def finish_benchmark(self, phases=None):
        """Public completion compatibility entry point.
        
        Keep this entry point on the concrete controller so completion callers
        do not depend on benchmark monkey-patching/import order.
        """
        from .motor_benchmark import _finish_benchmark
        return _finish_benchmark(self, list(phases or []))

    def finalize_benchmark_raw_log(self, raw_body=None):
        """Persist the completed benchmark Raw Log.

        This is the public finalization entry point used by benchmark
        completion code. It is deliberately idempotent for the current
        benchmark so STOP/finalization errors cannot create duplicate logs.
        """
        if raw_body is None:
            raw_body = (
                getattr(self, "measurement_raw_log", "")
                or getattr(self.serial, "raw_log", "")
                or ""
            )
        if not raw_body:
            return None
        if self.last_raw_log_id:
            return self.raw_log_library.get(self.last_raw_log_id)[0]
        return self._register_raw_log(raw_body)


    def _register_raw_log(self, raw_body=None):
        if raw_body is None:
            raw_body = getattr(self, "measurement_raw_log", "") or getattr(self.serial, "raw_log", "") or ""
        if not raw_body:
            return None

        session_id = getattr(self.session, "session_id", None)
        firmware = getattr(self.session, "firmware_version", "") or ""
        benchmark_type = getattr(self, "selected_benchmark_type", None) or getattr(self, "benchmark_type", None) or self.active_recipe_name or ""
        baseline_pwm = getattr(self, "benchmark_baseline_pwm", None)
        purpose = getattr(self, "benchmark_purpose", None)
        notes = ""
        if baseline_pwm is not None:
            notes = f"baseline_pwm={baseline_pwm}"
        if purpose:
            notes = f"{notes}; purpose={purpose}" if notes else f"purpose={purpose}"
        # RawLog IDs are string fields. Database-backed instance/session
        # identifiers may arrive as integers, but the Local Raw Log Library
        # uses these values as filesystem path components, so normalize the
        # identifier type at the persistence boundary.
        def normalize_id(value, field_name):
            if value is None or isinstance(value, str):
                return value
            if type(value) is int:
                return str(value)
            raise TypeError(
                f"{field_name} must be str, int, or None; got {type(value).__name__}"
            )

        instance_id = normalize_id(self.active_instance_id, "instance_id")
        session_id = normalize_id(session_id, "measurement_session_id")

        record = RawLog(
            device_type="MOTOR",
            firmware_version=firmware,
            device_instance_id=instance_id,
            motor_id=instance_id,
            measurement_session_id=session_id,
            acquired_at=datetime.now().isoformat(timespec="seconds"),
            measurement_condition=benchmark_type,
            notes=notes,
        )
        path = self.raw_log_library.register(record, raw_body)
        self.last_raw_log_id = record.log_id
        self.last_raw_log_path = path
        self._registered_raw_log_ids.append(record.log_id)
        return record
