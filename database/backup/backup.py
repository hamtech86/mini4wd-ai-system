# ============================================================
# backup.py
# Motor Database System
# Revision 1
# SQLite Database Backup Manager
# ============================================================

import sqlite3
import shutil
from pathlib import Path
from datetime import datetime



class BackupManager:


    def __init__(
        self,
        database_path,
        backup_directory
    ):

        self.database_path = Path(
            database_path
        )

        self.backup_directory = Path(
            backup_directory
        )


        self.backup_directory.mkdir(
            parents=True,
            exist_ok=True
        )



    def create_backup(self):

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )


        backup_file = (
            self.backup_directory /
            f"motor_database_backup_{timestamp}.db"
        )


        shutil.copy2(
            self.database_path,
            backup_file
        )


        return backup_file



    def restore_backup(
        self,
        backup_file
    ):

        backup_file = Path(
            backup_file
        )


        if not backup_file.exists():

            raise FileNotFoundError(
                "Backup file not found"
            )


        shutil.copy2(
            backup_file,
            self.database_path
        )



    def list_backups(self):

        files = []


        for file in self.backup_directory.glob(
            "motor_database_backup_*.db"
        ):

            files.append(
                file
            )


        return sorted(
            files,
            reverse=True
        )



    def remove_old_backups(
        self,
        keep_count=10
    ):

        backups = self.list_backups()


        for backup in backups[keep_count:]:

            backup.unlink()



    def verify_backup(
        self,
        backup_file
    ):

        backup_file = Path(
            backup_file
        )


        if not backup_file.exists():

            return False


        try:

            connection = sqlite3.connect(
                backup_file
            )


            cursor = connection.cursor()


            cursor.execute(
                """
                PRAGMA integrity_check;
                """
            )


            result = cursor.fetchone()


            connection.close()


            return result[0] == "ok"


        except Exception:

            return False



# ============================================================
# END OF backup.py
# ============================================================

