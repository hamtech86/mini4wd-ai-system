import sqlite3

import pytest

from database.repository.session_repository import SessionRepository
from measurement.measurement_session import MeasurementSession


class SQLiteDatabase:
    def __init__(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.connection.execute(
            """
            CREATE TABLE motor_instance (
                instance_id INTEGER PRIMARY KEY
            )
            """
        )
        self.connection.execute(
            "INSERT INTO motor_instance(instance_id) VALUES (7)"
        )
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
                measurement_type TEXT NOT NULL DEFAULT 'BREAKIN',
                FOREIGN KEY(instance_id) REFERENCES motor_instance(instance_id)
            )
            """
        )
        self.connection.commit()

    def execute(self, sql, params=()):
        cursor = self.connection.execute(sql, params)
        self.connection.commit()
        return cursor


def test_session_repository_binds_motor_instance():
    db = SQLiteDatabase()
    repository = SessionRepository(db)

    session = MeasurementSession(instance_id=7)
    session.start()
    repository.insert(session)

    row = repository.find(session.session_id)
    assert row["instance_id"] == 7


def test_session_repository_rejects_missing_motor_instance_before_insert():
    db = SQLiteDatabase()
    repository = SessionRepository(db)

    session = MeasurementSession()
    session.start()

    with pytest.raises(ValueError, match="instance_id is required"):
        repository.insert(session)
