#!/usr/bin/env python3
"""
Mini4WD Database Test
"""

import sqlite3
from pathlib import Path


DB_PATH = Path("database/mini4wd.db")


def main():

    print("=" * 60)
    print(" Mini4WD Database Test")
    print("=" * 60)

    # ---------------------------------------------------------
    # DB存在確認
    # ---------------------------------------------------------

    if not DB_PATH.exists():
        print(f"[ERROR] Database not found: {DB_PATH}")
        return

    print("[ OK ] Database file found")

    # ---------------------------------------------------------
    # 接続
    # ---------------------------------------------------------

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    print("[ OK ] Connected")

    # ---------------------------------------------------------
    # テーブル一覧
    # ---------------------------------------------------------

    cursor.execute("""
        SELECT name
        FROM sqlite_master
        WHERE type='table'
        ORDER BY name;
    """)

    tables = [row[0] for row in cursor.fetchall()]

    print("\nTables")

    for table in tables:
        print(f"  - {table}")

    required = [
        "schema_info",
        "motor_model",
        "motor_instance",
        "motor_work",
        "measurement_session",
        "breakin_log",
        "work_history",
    ]

    print()

    for table in required:

        if table in tables:
            print(f"[ OK ] {table}")
        else:
            print(f"[ NG ] {table}")

    # ---------------------------------------------------------
    # schema_version確認
    # ---------------------------------------------------------

    print()

    try:

        cursor.execute("""
            SELECT schema_version
            FROM schema_info
            LIMIT 1;
        """)

        row = cursor.fetchone()

        if row:
            print(f"[ OK ] Schema Version : {row[0]}")
        else:
            print("[ NG ] schema_info is empty")

    except Exception as e:

        print("[ NG ] schema_info read failed")
        print(e)

    conn.close()

    print("\nDatabase test finished.")


if __name__ == "__main__":
    main()

