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

from database.manager.database_manager import DatabaseManager
from measurement.measurement_session import MeasurementSession


class SessionRepository:
    """
    Measurement Session Repository
    """

    TABLE_NAME = "measurement_session"

    def __init__(
        self,
        database: DatabaseManager,
    ):

        self.database = database

    def insert(
        self,
        session: MeasurementSession,
    ):
        """
        Session追加
        """

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
        VALUES
        (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        )
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

    def update(
        self,
        session: MeasurementSession,
    ):
        """
        Session更新
        """

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
        WHERE
            session_id=?
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

    def find(
        self,
        session_id: str,
    ):
        """
        Session取得
        """

        sql = f"""
        SELECT *
        FROM {self.TABLE_NAME}
        WHERE session_id=?
        """

        cursor = self.database.execute(
            sql,
            (session_id,),
        )

        return cursor.fetchone()

    def find_all(self):
        """
        全Session取得
        """

        sql = f"""
        SELECT *
        FROM {self.TABLE_NAME}
        ORDER BY start_time DESC
        """

        cursor = self.database.execute(sql)

        return cursor.fetchall()

    def delete(
        self,
        session_id: str,
    ):
        """
        Session削除
        """

        sql = f"""
        DELETE
        FROM {self.TABLE_NAME}
        WHERE session_id=?
        """

        self.database.execute(
            sql,
            (session_id,),
        )

