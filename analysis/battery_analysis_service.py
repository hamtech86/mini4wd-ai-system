"""Service boundary from persisted Benchmark Result to Battery Analysis."""
from __future__ import annotations

from .battery_analysis import BatteryAnalysisResult, analyze_benchmark_result


class BatteryAnalysisService:
    """Read Benchmark Result data and generate a non-mutating analysis result."""

    def __init__(self, database):
        self.database = database

    def analyze_result(self, result_id: int) -> BatteryAnalysisResult:
        cursor = self.database.cursor()
        cursor.execute(
            "SELECT * FROM battery_benchmark_result WHERE result_id=?",
            (result_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"Battery Benchmark Result not found: {result_id}")
        result = dict(row) if hasattr(row, "keys") else self._row_to_dict(cursor, row)
        return analyze_benchmark_result(result)

    def analyze_session(self, session_id: str) -> BatteryAnalysisResult:
        cursor = self.database.cursor()
        cursor.execute(
            """SELECT * FROM battery_benchmark_result
               WHERE session_id=?
               ORDER BY result_id DESC
               LIMIT 1""",
            (session_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise ValueError(f"Battery Benchmark Result not found for session: {session_id}")
        result = dict(row) if hasattr(row, "keys") else self._row_to_dict(cursor, row)
        return analyze_benchmark_result(result)

    @staticmethod
    def _row_to_dict(cursor, row):
        return {description[0]: value for description, value in zip(cursor.description, row)}
