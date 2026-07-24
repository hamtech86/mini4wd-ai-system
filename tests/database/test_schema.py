import sqlite3


TABLES = {

    "schema_info",
    "motor_model",
    "motor_instance",
    "motor_work",
    "measurement_session",
    "breakin_log",
    "work_history"

}


def run():

    conn = sqlite3.connect("database/mini4wd.db")

    cur = conn.cursor()

    cur.execute(

        """
        SELECT name

        FROM sqlite_master

        WHERE type='table'
        """

    )

    result = {

        row[0]

        for row in cur.fetchall()

    }

    assert TABLES.issubset(result)

    conn.close()

