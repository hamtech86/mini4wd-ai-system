"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 measurement_repository.py
=====================================================

Measurement Repository

Measurementテーブルへのアクセスを担当する。
RepositoryはSQLのみを保持する。
"""

from __future__ import annotations

from dataclasses import fields

from measurement.measurement import Measurement
from database.manager.database_manager import DatabaseManager


class MeasurementRepository:
    """
    Measurement Repository
    """

    TABLE_NAME = "measurement"

    def __init__(
        self,
        database: DatabaseManager,
    ):

        self.database = database

    def insert(
        self,
        measurement: Measurement,
    ):
        """
        Measurementを1件保存
        """

        columns = [field.name for field in fields(Measurement)]

        values = [
            getattr(measurement, column)
            for column in columns
        ]

        placeholders = ",".join(
            "?" for _ in columns
        )

        sql = f"""
        INSERT INTO {self.TABLE_NAME}
        (
            {",".join(columns)}
        )
        VALUES
        (
            {placeholders}
        )
        """

        cursor = self.database.cursor()

        cursor.execute(sql, values)

        self.database.commit()

    def find_all(self):
        """
        全Measurement取得
        """

        cursor = self.database.cursor()

        cursor.execute(
            f"SELECT * FROM {self.TABLE_NAME}"
        )

        return cursor.fetchall()

    def delete_all(self):
        """
        全Measurement削除
        """

        cursor = self.database.cursor()

        cursor.execute(
            f"DELETE FROM {self.TABLE_NAME}"
        )

        self.database.commit()

    def count(self) -> int:
        """
        件数取得
        """

        cursor = self.database.cursor()

        cursor.execute(
            f"SELECT COUNT(*) FROM {self.TABLE_NAME}"
        )

        return cursor.fetchone()[0]

