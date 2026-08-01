"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 migration.py
=====================================================

Database Migration

初回起動時にSQLite Databaseと
テーブルを生成する。
"""

from __future__ import annotations

from pathlib import Path

from database.manager.database_manager import DatabaseManager


class Migration:
    """
    Database Migration
    """

    def __init__(
        self,
        database: DatabaseManager,
    ):

        self.database = database

        self.schema_file = (
            Path(__file__).parent.parent
            / "schema"
            / "create_tables.sql"
        )

    def migrate(self):
        """
        create_tables.sql を実行
        """

        if not self.schema_file.exists():
            raise FileNotFoundError(
                self.schema_file
            )

        self.database.connect()

        with open(
            self.schema_file,
            "r",
            encoding="utf-8",
        ) as file:

            sql = file.read()

        self.database.connection.executescript(sql)

        self.database.commit()

        print("Database initialized.")

