from database.manager.database_manager import DatabaseManager


def run():

    db = DatabaseManager("database/mini4wd.db")

    assert db.schema_version() == "Rev.1"

    db.close()

