"""Reset only Battery-specific data for development/bench verification.

Shared measurement_session / measurement tables are intentionally untouched.
Motor data is untouched.
"""
from __future__ import annotations
import sqlite3
import sys
from pathlib import Path

from database.path_resolver import connect_database, resolve_database_path


def reset(db_path: str | Path) -> None:
    path = resolve_database_path(db_path)
    with connect_database(path) as db:
        db.execute("PRAGMA foreign_keys = ON")
        db.execute("DELETE FROM battery_benchmark_result")
        db.execute("DELETE FROM battery_instance")
        db.execute("DELETE FROM battery_model")
        db.commit()

        schema = Path(__file__).resolve().parents[1] / "schema" / "battery_tables.sql"
        db.executescript(schema.read_text(encoding="utf-8"))
        db.commit()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m database.tools.reset_battery_data /absolute/path/to/existing.db")
    reset(sys.argv[1])
    print("Battery-specific data reset. Motor/shared measurement data were not deleted.")
