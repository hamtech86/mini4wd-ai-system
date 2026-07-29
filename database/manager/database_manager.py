"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 database_manager.py
=====================================================

Database Manager

Database層の窓口。

Controller・Repositoryはこのクラス経由で
SQLiteへアクセスする。

トランザクション管理も担当する。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path


class DatabaseManager:
    """
    Database Manager
    """

    def __init__(
        self,
        database_path: str = "database/mini4wd.db",
    ):

        self.database_path = Path(database_path)

        self.connection: sqlite3.Connection | None = None

    @property
    def is_connected(self) -> bool:
        """
        接続状態
        """

        return self.connection is not None

    def connect(self) -> sqlite3.Connection:
        """
        Database接続
        """

        if self.connection is None:

            self.connection = sqlite3.connect(
                self.database_path
            )

            # Rowを辞書風に扱えるようにする
            self.connection.row_factory = sqlite3.Row

            # 外部キー制約を有効化
            self.connection.execute(
                "PRAGMA foreign_keys = ON"
            )

        return self.connection

    def disconnect(self):
        """
        Database切断
        """

        if self.connection is not None:

            self.connection.close()

            self.connection = None

    def close(self):
        """
        disconnect()のエイリアス
        """

        self.disconnect()

    def cursor(self) -> sqlite3.Cursor:
        """
        Cursor取得
        """

        if self.connection is None:
            self.connect()

        return self.connection.cursor()

    # -------------------------------------------------
    # Transaction
    # -------------------------------------------------

    def begin(self):
        """
        トランザクション開始
        """

        if self.connection is None:
            self.connect()

        self.connection.execute("BEGIN")

    def commit(self):
        """
        コミット
        """

        if self.connection is not None:
            self.connection.commit()

    def rollback(self):
        """
        ロールバック
        """

        if self.connection is not None:
            self.connection.rollback()

    # -------------------------------------------------
    # Utility
    # -------------------------------------------------

    def execute(
        self,
        sql: str,
        parameters: tuple = (),
    ) -> sqlite3.Cursor:
        """
        SQL実行
        """

        cursor = self.cursor()
        cursor.execute(sql, parameters)

        return cursor

    def executemany(
        self,
        sql: str,
        parameters,
    ) -> sqlite3.Cursor:
        """
        SQL一括実行
        """

        cursor = self.cursor()
        cursor.executemany(sql, parameters)

        return cursor

