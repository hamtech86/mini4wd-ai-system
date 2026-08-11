import sqlite3
import unittest
from pathlib import Path

from motor_system.python.ui.benchmark_result_model import BenchmarkResult


class BenchmarkResultModelTest(unittest.TestCase):
    def test_normalizes_valid_result(self):
        result = BenchmarkResult(" 000001 ", " S001 ", "25500").normalized()
        self.assertEqual(result.instance_id, "000001")
        self.assertEqual(result.session_id, "S001")
        self.assertEqual(result.benchmark_rpm, 25500.0)

    def test_missing_ids_are_rejected(self):
        with self.assertRaises(ValueError):
            BenchmarkResult("", "S001", 25500).normalized()
        with self.assertRaises(ValueError):
            BenchmarkResult("000001", "", 25500).normalized()

    def test_non_positive_rpm_is_rejected(self):
        for rpm in (0, -1):
            with self.assertRaises(ValueError):
                BenchmarkResult("000001", "S001", rpm).normalized()


class BenchmarkResultSchemaTest(unittest.TestCase):
    def test_schema_can_be_applied_and_result_is_session_scoped(self):
        schema_dir = Path(__file__).parents[1] / "database" / "schema"
        con = sqlite3.connect(":memory:")
        con.execute("PRAGMA foreign_keys=ON")
        con.executescript(
            "CREATE TABLE measurement_session (session_id TEXT PRIMARY KEY);"
        )
        con.executescript((schema_dir / "benchmark_result.sql").read_text(encoding="utf-8"))
        con.execute("INSERT INTO measurement_session(session_id) VALUES ('S001')")
        con.execute(
            "INSERT INTO benchmark_result(instance_id, session_id, benchmark_rpm) VALUES (?, ?, ?)",
            ("000001", "S001", 25500.0),
        )
        row = con.execute(
            "SELECT instance_id, session_id, benchmark_rpm, source FROM benchmark_result"
        ).fetchone()
        self.assertEqual(row, ("000001", "S001", 25500.0, "USER_CONFIRMED"))

        with self.assertRaises(sqlite3.IntegrityError):
            con.execute(
                "INSERT INTO benchmark_result(instance_id, session_id, benchmark_rpm) VALUES (?, ?, ?)",
                ("000001", "S001", 26000.0),
            )

        con.close()


if __name__ == "__main__":
    unittest.main()
