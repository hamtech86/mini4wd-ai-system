import sqlite3

from database.repository.session_repository import SessionRepository
from measurement.measurement_session import MeasurementSession, MeasurementType


class LegacySQLiteDatabase:
    def __init__(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute(
            """
            CREATE TABLE measurement_session (
                session_id INTEGER PRIMARY KEY,
                instance_id INTEGER NOT NULL,
                device_type TEXT NOT NULL,
                device_model TEXT,
                firmware_version TEXT,
                analysis_version TEXT,
                calibration_profile TEXT,
                start_datetime DATETIME,
                end_datetime DATETIME,
                operator TEXT,
                result TEXT,
                notes TEXT,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME,
                measurement_type TEXT NOT NULL DEFAULT 'BREAKIN'
            )
            """
        )

    def execute(self, sql, params=()):
        cursor = self.connection.execute(sql, params)
        self.connection.commit()
        return cursor


def test_legacy_session_repository_insert_and_update():
    db = LegacySQLiteDatabase()
    repository = SessionRepository(db)

    session = MeasurementSession(measurement_type=MeasurementType.BREAKIN)
    session.start()

    repository.insert(session)

    assert session.session_id.isdigit()
    row = repository.find(session.session_id)
    assert row["measurement_type"] == "BREAKIN"
    assert row["result"] == "RUNNING"
    assert row["device_type"] == "BREAKIN"

    session.finish()
    session.measurement_count = 3
    repository.update(session)

    row = repository.find(session.session_id)
    assert row["result"] == "COMPLETE"
    assert row["end_datetime"] is not None


def test_legacy_session_repository_find_all_uses_start_datetime():
    db = LegacySQLiteDatabase()
    repository = SessionRepository(db)

    first = MeasurementSession()
    first.start()
    repository.insert(first)

    second = MeasurementSession()
    second.start()
    repository.insert(second)

    rows = repository.find_all()
    assert len(rows) == 2
