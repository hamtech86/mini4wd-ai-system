#!/usr/bin/env python3
"""
motor_instance CRUD Test
"""

import sqlite3
from pathlib import Path

DB_PATH = Path("database/mini4wd.db")


def main():

    print("=" * 60)
    print("Motor Instance CRUD Test")
    print("=" * 60)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # ---------------------------------------------------------
    # モーターモデル取得
    # ---------------------------------------------------------

    cursor.execute("""
        SELECT motor_model_id, name
        FROM motor_model
        LIMIT 1;
    """)

    model = cursor.fetchone()

    if model is None:
        print("[ERROR] motor_model が登録されていません。")
        return

    model_id = model[0]

    print(f"[ OK ] 使用モデル : {model[1]} (ID={model_id})")

    # ---------------------------------------------------------
    # Create
    # ---------------------------------------------------------

    cursor.execute("""
        INSERT INTO motor_instance
        (
            motor_model_id,
            serial_number,
            nickname,
            status
        )
        VALUES
        (
            ?, ?, ?, ?
        );
    """,
    (
        model_id,
        "TEST001",
        "テストモーター",
        "NEW"
    ))

    instance_id = cursor.lastrowid

    conn.commit()

    print(f"[ OK ] 作成 Instance ID = {instance_id}")

    # ---------------------------------------------------------
    # Read
    # ---------------------------------------------------------

    cursor.execute("""
        SELECT
            instance_id,
            nickname,
            status
        FROM motor_instance
        WHERE instance_id=?;
    """, (instance_id,))

    row = cursor.fetchone()

    print("[ OK ] 読み込み成功")
    print(row)

    # ---------------------------------------------------------
    # Update
    # ---------------------------------------------------------

    cursor.execute("""
        UPDATE motor_instance

        SET
            nickname=?,
            status=?

        WHERE
            instance_id=?;
    """,
    (
        "更新後モーター",
        "ACTIVE",
        instance_id
    ))

    conn.commit()

    print("[ OK ] 更新成功")

    # ---------------------------------------------------------
    # Confirm Update
    # ---------------------------------------------------------

    cursor.execute("""
        SELECT nickname,status

        FROM motor_instance

        WHERE instance_id=?;
    """, (instance_id,))

    print("[ OK ] 更新確認")

    print(cursor.fetchone())

    # ---------------------------------------------------------
    # Soft Delete
    # ---------------------------------------------------------

    cursor.execute("""
        UPDATE motor_instance

        SET
            is_deleted=1

        WHERE
            instance_id=?;
    """, (instance_id,))

    conn.commit()

    print("[ OK ] 論理削除成功")

    # ---------------------------------------------------------
    # Confirm Delete
    # ---------------------------------------------------------

    cursor.execute("""
        SELECT is_deleted

        FROM motor_instance

        WHERE instance_id=?;
    """, (instance_id,))

    print("[ OK ] 削除確認")

    print(cursor.fetchone())

    conn.close()

    print("\n========== ALL TEST PASSED ==========")


if __name__ == "__main__":
    main()

