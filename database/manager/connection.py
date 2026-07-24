# ============================================================
# connection.py
# Motor Database System
# Revision 1
# SQLite3 Database Connection Manager
# ============================================================

import sqlite3
from pathlib import Path


class DatabaseConnection:

    def __init__(self, db_path):

        self.db_path = Path(db_path)

        self.connection = None


    def connect(self):

        if self.connection is None:

            self.connection = sqlite3.connect(
                self.db_path
            )

            self.connection.row_factory = sqlite3.Row


            self.enable_foreign_keys()


        return self.connection



    def enable_foreign_keys(self):

        cursor = self.connection.cursor()

        cursor.execute(
            "PRAGMA foreign_keys = ON;"
        )

        cursor.close()



    def close(self):

        if self.connection:

            self.connection.close()

            self.connection = None



    def execute(
        self,
        query,
        parameters=None
    ):

        conn = self.connect()

        cursor = conn.cursor()


        if parameters:

            cursor.execute(
                query,
                parameters
            )

        else:

            cursor.execute(
                query
            )


        return cursor



    def execute_many(
        self,
        query,
        data
    ):

        conn = self.connect()

        cursor = conn.cursor()


        cursor.executemany(
            query,
            data
        )


        return cursor



    def commit(self):

        if self.connection:

            self.connection.commit()



    def rollback(self):

        if self.connection:

            self.connection.rollback()



    def begin_transaction(self):

        conn = self.connect()

        conn.execute(
            "BEGIN;"
        )



    def table_exists(
        self,
        table_name
    ):

        cursor = self.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type='table'
            AND name=?
            """,
            (
                table_name,
            )
        )


        result = cursor.fetchone()


        return result is not None



# ============================================================
# END OF connection.py
# ============================================================

