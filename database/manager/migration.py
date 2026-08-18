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
        schema_dir = Path(__file__).parent.parent / "schema"
        self.schema_file = schema_dir / "create_tables.sql"
        self.battery_schema_file = schema_dir / "battery_tables.sql"

    def migrate(self):
        """Execute the common and Battery database schemas."""
        if not self.schema_file.exists():
            raise FileNotFoundError(self.schema_file)
        if not self.battery_schema_file.exists():
            raise FileNotFoundError(self.battery_schema_file)

        self.database.connect()

        with open(self.schema_file, "r", encoding="utf-8") as file:
            sql = file.read()
        self.database.connection.executescript(sql)

        with open(self.battery_schema_file, "r", encoding="utf-8") as file:
            battery_sql = file.read()
        self.database.connection.executescript(battery_sql)

        self.database.commit()
        print("Database initialized.")
