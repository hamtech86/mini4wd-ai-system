"""
DatabaseManager Integration Test
"""

from database.manager.database_manager import DatabaseManager


def main():

    print("=" * 60)
    print("DatabaseManager Test")
    print("=" * 60)

    db = DatabaseManager("database/mini4wd.db")

    # -------------------------------------------------
    # モーターモデル取得
    # -------------------------------------------------

    models = db.motor.get_all()

    print(f"[OK] Motor Models : {len(models)}")

    if not models:
        raise RuntimeError("motor_model is empty.")

    model = models[0]

    print(model)

    # -------------------------------------------------
    # インスタンス作成
    # -------------------------------------------------

    instance = {

        "motor_model_id": model["motor_model_id"],

        "serial_number": "TEST-001",

        "nickname": "DBManager Test",

        "status": "NEW"

    }

    instance_id = db.motor_instance.create(instance)

    print(f"[OK] Instance Created : {instance_id}")

    # -------------------------------------------------
    # 取得
    # -------------------------------------------------

    result = db.motor_instance.get_by_id(instance_id)

    print(result)

    # -------------------------------------------------
    # 更新
    # -------------------------------------------------

    db.motor_instance.update_instance(

        instance_id,

        {

            "nickname": "Updated",

            "status": "ACTIVE"

        }

    )

    print("[OK] Updated")

    # -------------------------------------------------
    # 論理削除
    # -------------------------------------------------

    db.motor_instance.delete(instance_id)

    print("[OK] Deleted")

    db.close()

    print("\n========== PASS ==========")


if __name__ == "__main__":

    main()

