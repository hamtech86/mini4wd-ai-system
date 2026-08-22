"""Reset only Battery-specific data for development/bench verification.

Shared measurement_session / measurement tables are intentionally untouched.
Motor data is untouched.
"""
from __future__ import annotations
import sqlite3
import sys
from pathlib import Path


def reset(db_path: str | Path) -> None:
    path = Path(db_path)
    if not path.exists():
        raise FileNotFoundError(path)
    with sqlite3.connect(path) as db:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("DELETE FROM battery_benchmark_result")
        db.execute("DELETE FROM battery_instance")
        db.execute("DELETE FROM battery_model")
        db.commit()

        schema = Path(__file__).resolve().parents[1] / "schema" / "battery_tables.sql"
        db.executescript(schema.read_text(encoding="utf-8"))
        db.commit()


if __name__ == "__main__":
    reset(sys.argv[1] if len(sys.argv) > 1 else "database/mini4wd.db")
    print("Battery-specific data reset. Motor/shared measurement data were not deleted.")
