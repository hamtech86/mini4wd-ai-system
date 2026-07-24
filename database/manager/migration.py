# ============================================================
# migration.py
# Motor Database System
# Revision 1
# SQLite3 Schema Migration Manager
# ============================================================

import sqlite3
from datetime import datetime



class MigrationManager:


    CURRENT_VERSION = "Rev.1"



    def __init__(
        self,
        database
    ):

        self.database = database



    def get_schema_version(self):

        cursor = self.database.execute(
            """
            SELECT schema_version
            FROM schema_info
            LIMIT 1
            """
        )


        row = cursor.fetchone()


        if row:

            return row["schema_version"]


        return None



    def set_schema_version(
        self,
        version,
        description=None
    ):

        self.database.execute(
            """
            UPDATE schema_info

            SET
                schema_version=?,
                description=?,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                version,
                description
            )
        )


        self.database.commit()



    def check_version(self):

        version = self.get_schema_version()


        if version == self.CURRENT_VERSION:

            return True


        return False



    def migrate(self):

        current = self.get_schema_version()


        if current is None:

            self.initialize_schema()


        elif current != self.CURRENT_VERSION:

            self.apply_migration(
                current,
                self.CURRENT_VERSION
            )



    def initialize_schema(self):

        self.set_schema_version(
            self.CURRENT_VERSION,
            "Initial schema creation"
        )



    def apply_migration(
        self,
        old_version,
        new_version
    ):

        migrations = {


            # Future migrations

            # "Rev.1": [
            #     migration_function
            # ]

        }


        if old_version in migrations:


            for migration in migrations[old_version]:

                migration()


        self.set_schema_version(
            new_version,
            f"Migration {old_version} -> {new_version}"
        )



    def backup_required(
        self,
        old_version,
        new_version
    ):

        if old_version != new_version:

            return True


        return False



# ============================================================
# END OF migration.py
# ============================================================

