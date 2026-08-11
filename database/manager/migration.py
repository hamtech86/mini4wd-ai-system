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
        schema_dir = Path(__file__).parent.parent / "schema"
        self.schema_file = schema_dir / "create_tables.sql"
        self.benchmark_schema_file = schema_dir / "benchmark_result.sql"
        self.database = database

    def migrate(self):
        """Create/update the database schema idempotently."""
        for schema_file in (self.schema_file, self.benchmark_schema_file):
            if not schema_file.exists():
                raise FileNotFoundError(schema_file)

        self.database.connect()

        for schema_file in (self.schema_file, self.benchmark_schema_file):
            with open(schema_file, "r", encoding="utf-8") as file:
                self.database.connection.executescript(file.read())

        self.database.commit()
        print("Database initialized.")
