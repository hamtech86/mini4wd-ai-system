"""Migrate Battery Benchmark v2 and backfill derived fields from raw Measurement.

This migration is additive. It never deletes or rewrites raw Measurement rows.
It adds the analysis-critical fields, installs the automatic derivation trigger,
and backfills existing Benchmark Result rows from their linked Measurement
session when possible.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "mini4wd.db"

TRIGGER_SQL = """
CREATE TRIGGER IF NOT EXISTS trg_battery_benchmark_derive_measurement_fields
AFTER INSERT ON battery_benchmark_result
FOR EACH ROW
BEGIN
    UPDATE battery_benchmark_result
       SET start_voltage = (
               SELECT COALESCE(voltage1, voltage2) FROM measurement
                WHERE session_id = NEW.session_id
                  AND COALESCE(voltage1, voltage2) IS NOT NULL
                ORDER BY elapsed_time ASC
                LIMIT 1
           ),
           end_voltage = (
               SELECT COALESCE(voltage1, voltage2) FROM measurement
                WHERE session_id = NEW.session_id
                  AND COALESCE(voltage1, voltage2) IS NOT NULL
                ORDER BY elapsed_time DESC
                LIMIT 1
           ),
           voltage_drop = (
               SELECT COALESCE(voltage1, voltage2) FROM measurement
                WHERE session_id = NEW.session_id
                  AND COALESCE(voltage1, voltage2) IS NOT NULL
                ORDER BY elapsed_time ASC
                LIMIT 1
           ) - (
               SELECT COALESCE(voltage1, voltage2) FROM measurement
                WHERE session_id = NEW.session_id
                  AND COALESCE(voltage1, voltage2) IS NOT NULL
                ORDER BY elapsed_time DESC
                LIMIT 1
           )
     WHERE result_id = NEW.result_id;
END;
"""


def main():
    with sqlite3.connect(DB_PATH) as db:
        cols = {row[1] for row in db.execute("PRAGMA table_info(battery_benchmark_result)")}
        for name in ("start_voltage", "end_voltage", "voltage_drop"):
            if name not in cols:
                db.execute(f"ALTER TABLE battery_benchmark_result ADD COLUMN {name} REAL")

        measurement_cols = {row[1] for row in db.execute("PRAGMA table_info(measurement)")}
        required = {"session_id", "elapsed_time", "voltage1", "voltage2"}
        missing = required - measurement_cols
        if missing:
            raise RuntimeError("measurement schema is missing required columns: " + ", ".join(sorted(missing)))

        db.executescript(TRIGGER_SQL)
        rows = db.execute("SELECT result_id, session_id FROM battery_benchmark_result").fetchall()
        updated = 0
        for result_id, session_id in rows:
            first = db.execute(
                """SELECT COALESCE(voltage1, voltage2) FROM measurement
                   WHERE session_id=? AND COALESCE(voltage1, voltage2) IS NOT NULL
                   ORDER BY elapsed_time ASC, id ASC LIMIT 1""", (session_id,)
            ).fetchone()
            last = db.execute(
                """SELECT COALESCE(voltage1, voltage2) FROM measurement
                   WHERE session_id=? AND COALESCE(voltage1, voltage2) IS NOT NULL
                   ORDER BY elapsed_time DESC, id DESC LIMIT 1""", (session_id,)
            ).fetchone()
            if first is None or last is None:
                continue
            start_voltage = float(first[0]); end_voltage = float(last[0])
            db.execute(
                "UPDATE battery_benchmark_result SET start_voltage=?, end_voltage=?, voltage_drop=? WHERE result_id=?",
                (start_voltage, end_voltage, start_voltage - end_voltage, result_id),
            )
            updated += 1
        db.commit()
        print(f"Battery Benchmark v2 ready. Existing results backfilled: {updated}/{len(rows)}")


if __name__ == "__main__":
    main()
