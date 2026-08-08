"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 session_repository.py
=====================================================

Measurement Session Repository

measurement_sessionテーブルへのアクセスを担当する。

RepositoryはSQLのみを保持する。
"""

from __future__ import annotations

from datetime import datetime

from database.manager.database_manager import DatabaseManager
from measurement.measurement_session import MeasurementSession, SessionStatus


class SessionRepository:
    """Measurement Session Repository."""

    TABLE_NAME = "measurement_session"

    def __init__(self, database: DatabaseManager):
        self.database = database

    def _columns(self) -> set[str]:
        rows = self.database.execute(
            f"PRAGMA table_info({self.TABLE_NAME})"
        ).fetchall()
        return {row[1] for row in rows}

    def _is_legacy_schema(self, columns: set[str] | None = None) -> bool:
        columns = columns if columns is not None else self._columns()
        return "instance_id" in columns and "start_datetime" in columns

    @staticmethod
    def _timestamp(value: datetime | None):
        return value.isoformat() if value is not None else None

    @staticmethod
    def _legacy_result(status: SessionStatus) -> str:
        return {
            SessionStatus.READY: "READY",
            SessionStatus.RUNNING: "RUNNING",
            SessionStatus.FINISHED: "COMPLETE",
            SessionStatus.CANCELLED: "CANCELLED",
            SessionStatus.ERROR: "ERROR",
        }[status]

    @staticmethod
    def _require_instance_id(session: MeasurementSession) -> int:
        """Return a valid DB motor instance id or fail before the FK INSERT."""
        if session.instance_id is None:
            raise ValueError(
                "MeasurementSession.instance_id is required for database persistence"
            )
        try:
            instance_id = int(session.instance_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("MeasurementSession.instance_id must be an integer") from exc
        if instance_id <= 0:
            raise ValueError("MeasurementSession.instance_id must be a positive integer")
        return instance_id

    def _allocate_legacy_session_id(self, session: MeasurementSession):
        """Allocate an integer-compatible ID for the pre-Phase1 schema."""
        try:
            value = int(session.session_id)
            session.session_id = str(value)
            return
        except (TypeError, ValueError):
            pass

        row = self.database.execute(
            f"SELECT COALESCE(MAX(session_id), 0) + 1 FROM {self.TABLE_NAME}"
        ).fetchone()
        session.session_id = str(row[0])

    def insert(self, session: MeasurementSession):
        """Session追加."""
        columns = self._columns()

        if self._is_legacy_schema(columns):
            instance_id = self._require_instance_id(session)
            self._allocate_legacy_session_id(session)
            sql = f"""
            INSERT INTO {self.TABLE_NAME}
            (
                session_id,
                instance_id,
                device_type,
                device_model,
                firmware_version,
                analysis_version,
                calibration_profile,
                start_datetime,
                end_datetime,
                operator,
                result,
                notes,
                measurement_type
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            self.database.execute(
                sql,
                (
                    session.session_id,
                    instance_id,
                    "BREAKIN",
                    "MOTOR_BREAKIN_V3",
                    session.firmware_version,
                    session.schema_version,
                    None,
                    self._timestamp(session.start_time),
                    self._timestamp(session.end_time),
                    session.operator,
                    self._legacy_result(session.status),
                    session.notes,
                    session.measurement_type.value,
                ),
            )
            return

        sql = f"""
        INSERT INTO {self.TABLE_NAME}
        (
            session_id,
            measurement_type,
            status,
            start_time,
            end_time,
            measurement_count,
            operator,
            notes,
            schema_version,
            firmware_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        self.database.execute(
            sql,
            (
                session.session_id,
                session.measurement_type.value,
                session.status.value,
                session.start_time,
                session.end_time,
                session.measurement_count,
                session.operator,
                session.notes,
                session.schema_version,
                session.firmware_version,
            ),
        )

    def update(self, session: MeasurementSession):
        """Session更新."""
        columns = self._columns()

        if self._is_legacy_schema(columns):
            assignments = [
                "end_datetime=?",
                "result=?",
                "operator=?",
                "notes=?",
                "measurement_type=?",
                "firmware_version=?",
            ]
            parameters = [
                self._timestamp(session.end_time),
                self._legacy_result(session.status),
                session.operator,
                session.notes,
                session.measurement_type.value,
                session.firmware_version,
            ]
            if "updated_at" in columns:
                assignments.append("updated_at=CURRENT_TIMESTAMP")

            sql = f"""
            UPDATE {self.TABLE_NAME}
            SET {", ".join(assignments)}
            WHERE session_id=?
            """
            parameters.append(session.session_id)
            self.database.execute(sql, tuple(parameters))
            return

        sql = f"""
        UPDATE {self.TABLE_NAME}
        SET
            status=?,
            end_time=?,
            measurement_count=?,
            operator=?,
            notes=?,
            schema_version=?,
            firmware_version=?
        WHERE session_id=?
        """
        self.database.execute(
            sql,
            (
                session.status.value,
                session.end_time,
                session.measurement_count,
                session.operator,
                session.notes,
                session.schema_version,
                session.firmware_version,
                session.session_id,
            ),
        )

    def find(self, session_id: str):
        """Session取得."""
        sql = f"SELECT * FROM {self.TABLE_NAME} WHERE session_id=?"
        return self.database.execute(sql, (session_id,)).fetchone()

    def find_all(self):
        """全Session取得."""
        columns = self._columns()
        order_column = "start_datetime" if self._is_legacy_schema(columns) else "start_time"
        sql = f"SELECT * FROM {self.TABLE_NAME} ORDER BY {order_column} DESC"
        return self.database.execute(sql).fetchall()

    def delete(self, session_id: str):
        """Session削除."""
        sql = f"DELETE FROM {self.TABLE_NAME} WHERE session_id=?"
        self.database.execute(sql, (session_id,))
