import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCHEMA = ROOT / "database" / "schema" / "create_tables.sql"
MIGRATION = ROOT / "database" / "migrations" / "003_benchmark_voltage_mode.sql"


def test_migration_adds_canonical_fields_without_reclassifying_existing_rows():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row

    # Legacy shape intentionally omits the new fields.
    db.executescript("""
    CREATE TABLE measurement_session (
        session_id TEXT PRIMARY KEY,
        measurement_type TEXT NOT NULL,
        status TEXT NOT NULL,
        start_time TEXT,
        end_time TEXT,
        measurement_count INTEGER DEFAULT 0,
        operator TEXT,
        notes TEXT,
        schema_version TEXT,
        firmware_version TEXT
    );
    INSERT INTO measurement_session
      (session_id, measurement_type, status, notes)
    VALUES
      ('S1', 'BREAKIN', 'FINISHED', 'benchmark_type=STANDARD_3V30S; purpose=MEASUREMENT');
    """)

    db.executescript(MIGRATION.read_text(encoding="utf-8"))

    columns = {row["name"] for row in db.execute("PRAGMA table_info(measurement_session)")}
    assert "benchmark_type_code" in columns
    assert "voltage_control_mode" in columns

    row = db.execute(
        "SELECT benchmark_type_code, voltage_control_mode, notes "
        "FROM measurement_session WHERE session_id='S1'"
    ).fetchone()

    # Existing data is intentionally left unclassified.
    assert row["benchmark_type_code"] is None
    assert row["voltage_control_mode"] is None
    assert row["notes"] == "benchmark_type=STANDARD_3V30S; purpose=MEASUREMENT"


def test_new_canonical_pairs_are_distinguishable():
    db = sqlite3.connect(":memory:")
    db.executescript(SCHEMA.read_text(encoding="utf-8"))

    rows = [
        ("S1", "STANDARD", "TERMINAL"),
        ("S2", "STANDARD", "INPUT"),
        ("S3", "FULL_PACKAGE", "TERMINAL"),
        ("S4", "FULL_PACKAGE", "INPUT"),
    ]

    for sid, benchmark, mode in rows:
        db.execute(
            """INSERT INTO measurement_session
               (session_id, measurement_type, status,
                benchmark_type_code, voltage_control_mode)
               VALUES (?, 'BREAKIN', 'FINISHED', ?, ?)""",
            (sid, benchmark, mode),
        )

    result = db.execute(
        """SELECT benchmark_type_code, voltage_control_mode
           FROM measurement_session ORDER BY session_id"""
    ).fetchall()

    assert [(r[0], r[1]) for r in result] == [(b, m) for _, b, m in rows]
