"""Persistence boundary for Battery 5A benchmark analysis.

The service reads Measurement rows and writes only derived Benchmark Result
rows. It deliberately does not update Measurement data or calculate internal
resistance.
"""

from __future__ import annotations

from analysis.battery_benchmark import analyze_5a_measurements
from database.repository.battery_repository import BatteryBenchmarkResultRepository


class BatteryBenchmarkService:
    def __init__(self, database):
        self.database = database
        self.results = BatteryBenchmarkResultRepository(database)
        self.results.ensure_schema()

    def analyze_session(self, session_id: str, instance_id: str | None = None):
        rows = self._load_measurements(session_id)
        result = analyze_5a_measurements(rows)
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
