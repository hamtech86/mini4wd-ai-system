"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 database_manager.py
=====================================================

Database Manager

SQLiteデータベースへの接続管理を担当する。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Optional


class DatabaseManager:
    """SQLite Database Manager."""

    def __init__(self, database_path: str = "database/mini4wd.db"):
        self.database_path = Path(database_path)
        self.connection: Optional[sqlite3.Connection] = None

    @property
    def is_connected(self) -> bool:
        return self.connection is not None

    def connect(self) -> sqlite3.Connection:
        """Connect to SQLite and perform non-destructive schema migration."""
        if self.connection is None:
            self.database_path.parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(
                self.database_path,
                check_same_thread=False,
            )
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA foreign_keys = ON")
            self._migrate_schema()
        return self.connection

    def _migrate_schema(self) -> None:
        """Bring an existing measurement_session table up to the current schema."""
        assert self.connection is not None
        columns = {
            row[1]
            for row in self.connection.execute(
                "PRAGMA table_info(measurement_session)"
            ).fetchall()
        }
        if not columns:
            return

        # Older local databases may predate measurement_type.
        if "measurement_type" not in columns:
            self.connection.execute(
                "ALTER TABLE measurement_session "
                "ADD COLUMN measurement_type TEXT NOT NULL DEFAULT 'BREAKIN'"
            )
            self.connection.commit()

    def disconnect(self):
        if self.connection is not None:
            self.connection.close()
            self.connection = None

    def close(self):
        self.disconnect()

    def cursor(self) -> sqlite3.Cursor:
        if self.connection is None:
            self.connect()
        return self.connection.cursor()

    def begin(self):
        if self.connection is None:
            self.connect()
        self.connection.execute("BEGIN")

    def commit(self):
        if self.connection is not None:
            self.connection.commit()

    def rollback(self):
        if self.connection is not None:
            self.connection.rollback()

    def execute(self, sql: str, parameters: tuple = ()) -> sqlite3.Cursor:
        cursor = self.cursor()
        cursor.execute(sql, parameters)
        return cursor

    def executemany(self, sql: str, parameters: Iterable) -> sqlite3.Cursor:
        cursor = self.cursor()
        cursor.executemany(sql, parameters)
        return cursor

    def executescript(self, sql: str):
        if self.connection is None:
            self.connect()
        self.connection.executescript(sql)

    def table_exists(self, table_name: str) -> bool:
        cursor = self.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        )
        return cursor.fetchone() is not None

    def vacuum(self):
        if self.connection is None:
            self.connect()
        self.connection.execute("VACUUM")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.commit()
        else:
            self.rollback()
        self.disconnect()
