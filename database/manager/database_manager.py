"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 database_manager.py
=====================================================

Database Manager

SQLiteデータベースへの接続管理を担当する。

責務
-----------------------------------------
・Database接続
・切断
・Cursor取得
・Transaction管理
・SQL実行補助

SQL文自体はRepository層のみが保持する。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Optional


class DatabaseManager:
    """
    SQLite Database Manager
    """

    def __init__(
        self,
        database_path: str = "database/mini4wd.db",
    ):

        self.database_path = Path(database_path)

        self.connection: Optional[sqlite3.Connection] = None

    # =================================================
    # Connection
    # =================================================

    @property
    def is_connected(self) -> bool:
        """接続状態"""

        return self.connection is not None

    def connect(self) -> sqlite3.Connection:
        """
        Database接続
        """

        if self.connection is None:

            self.connection = sqlite3.connect(
                self.database_path
            )

            # Rowを辞書のように扱う
            self.connection.row_factory = sqlite3.Row

            # 外部キー制約有効
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

    # =================================================
    # Cursor
    # =================================================

    def cursor(self) -> sqlite3.Cursor:
        """
        Cursor取得
        """

        if self.connection is None:
            self.connect()

        return self.connection.cursor()

    # =================================================
    # Transaction
    # =================================================

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

    # =================================================
    # Execute
    # =================================================

    def execute(
        self,
        sql: str,
        parameters: tuple = (),
    ) -> sqlite3.Cursor:
        """
        SQL実行
        """

        cursor = self.cursor()

        cursor.execute(
            sql,
            parameters,
        )

        return cursor

    def executemany(
        self,
        sql: str,
        parameters: Iterable,
    ) -> sqlite3.Cursor:
        """
        SQL一括実行
        """

        cursor = self.cursor()

        cursor.executemany(
            sql,
            parameters,
        )

        return cursor

    def executescript(
        self,
        sql: str,
    ):
        """
        SQLスクリプト実行
        """

        if self.connection is None:
            self.connect()

        self.connection.executescript(sql)

    # =================================================
    # Utility
    # =================================================

    def table_exists(
        self,
        table_name: str,
    ) -> bool:
        """
        テーブル存在確認
        """

        cursor = self.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
              AND name=?
            """,
            (table_name,),
        )

        return cursor.fetchone() is not None

    def vacuum(self):
        """
        Database最適化
        """

        if self.connection is None:
            self.connect()

        self.connection.execute("VACUUM")

    def __enter__(self):
        """
        with対応
        """

        self.connect()

        return self

    def __exit__(
        self,
        exc_type,
        exc_val,
        exc_tb,
    ):
        """
        with終了処理
        """

        if exc_type is None:
            self.commit()
        else:
            self.rollback()

        self.disconnect()

