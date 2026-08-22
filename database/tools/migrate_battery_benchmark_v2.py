"""Additive migration for Battery Benchmark v2 fields.

Adds start/end voltage without touching shared measurement data.
Existing benchmark rows are preserved; new fields remain NULL until
recomputed from the original measurement session.
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "mini4wd.db"


def main():
    db = sqlite3.connect(DB_PATH)
    try:
        cols = {row[1] for row in db.execute("PRAGMA table_info(battery_benchmark_result)")}
        for name in ("start_voltage", "end_voltage"):
            if name not in cols:
                db.execute(f"ALTER TABLE battery_benchmark_result ADD COLUMN {name} REAL")
        db.commit()
        print("Battery Benchmark v2 schema ready: start_voltage, end_voltage")
    finally:
        db.close()


if __name__ == "__main__":
    main()
