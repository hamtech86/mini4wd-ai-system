"""Persistence boundary for explicitly channel-scoped Battery analysis."""
from __future__ import annotations

from analysis.battery_benchmark import analyze_5a_measurements
from database.repository.battery_repository import BatteryBenchmarkResultRepository


class BatteryBenchmarkService:
    def __init__(self, database):
        self.database = database
        self.results = BatteryBenchmarkResultRepository(database)
        self.results.ensure_schema()

    def analyze_session(self, session_id: str, *, channel: str, instance_id: str | None = None):
        if channel not in ("CH1", "CH2"):
            raise ValueError("channel must be explicitly set to 'CH1' or 'CH2'")
        self._validate_scope_identity(session_id, channel)
        rows = self._load_measurements(session_id)
        result = analyze_5a_measurements(rows, channel=channel)
        result.update({"session_id": session_id, "instance_id": instance_id})
        persisted = {key: value for key, value in result.items() if key != "channel"}
        self.results.save(persisted)
        return result

    def _validate_scope_identity(self, session_id: str, channel: str):
        """Reject analysis unless Session and every Measurement persist the requested Scope Key."""
        cursor = self.database.cursor()
        session_columns = {
            row[1] for row in cursor.execute("PRAGMA table_info(measurement_session)").fetchall()
        }
        measurement_columns = {
            row[1] for row in cursor.execute("PRAGMA table_info(measurement)").fetchall()
        }
        if "scope_key" not in session_columns or "scope_key" not in measurement_columns:
            raise ValueError("Scope Key validity is UNKNOWN: persisted Scope Key is unavailable")

        session = cursor.execute(
            "SELECT scope_key FROM measurement_session WHERE session_id=?", (session_id,)
        ).fetchone()
        expected_scope = f"BATTERY:{channel}"
        if session is None or session[0] != expected_scope:
            raise ValueError("Scope Key validity is UNKNOWN: Session Scope Key does not match requested channel")

        measurement_scopes = cursor.execute(
            "SELECT scope_key FROM measurement WHERE session_id=? ORDER BY id", (session_id,)
        ).fetchall()
        if not measurement_scopes or any(row[0] != expected_scope for row in measurement_scopes):
            raise ValueError("Scope Key validity is UNKNOWN: Measurement Scope Keys are missing or inconsistent")

    def _load_measurements(self, session_id: str):
        cursor = self.database.cursor()
        cursor.execute(
            "SELECT * FROM measurement WHERE session_id=? ORDER BY elapsed_time, id",
            (session_id,),
        )
        return [dict(row) for row in cursor.fetchall()]
