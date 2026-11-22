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
        rows = self._load_measurements(session_id)
        result = analyze_5a_measurements(rows, channel=channel)
        result.update({"session_id": session_id, "instance_id": instance_id})
        self.results.save(result)
        return result

    def _load_measurements(self, session_id: str):
        cursor = self.database.cursor()
        cursor.execute(
            "SELECT * FROM measurement WHERE session_id=? ORDER BY elapsed_time, id",
            (session_id,),
        )
        return [dict(row) for row in cursor.fetchall()]
