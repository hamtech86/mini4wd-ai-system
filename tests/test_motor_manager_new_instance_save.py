from pathlib import Path
import sqlite3


UI_PATH = Path(__file__).parents[1] / "motor_system" / "python" / "ui" / "motor_manager_ui.py"


def test_motor_instance_repository_create_allocates_id_and_persists():
    from database.repository.motor_instance_repository import MotorInstanceRepository

    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute(
        """
        CREATE TABLE motor_instance (
            instance_id INTEGER PRIMARY KEY AUTOINCREMENT,
            motor_model_id INTEGER NOT NULL,
            serial_number TEXT,
            nickname TEXT,
            status TEXT,
            is_deleted INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    repo = MotorInstanceRepository(db)
    first_id = repo.create(
        {
            "motor_model_id": 1,
            "serial_number": "NEW-TEST-001",
            "nickname": "New Instance Test",
            "status": "NEW",
        }
    )

    assert first_id == 1
    row = repo.get_by_id(first_id)
    assert row["motor_model_id"] == 1
    assert row["serial_number"] == "NEW-TEST-001"

    repo.update_instance(first_id, {"nickname": "Updated Instance"})
    assert repo.get_by_id(first_id)["nickname"] == "Updated Instance"

    # A second save after the UI has adopted the returned ID must update,
    # not create another instance.
    repo.update_instance(first_id, {"status": "ACTIVE"})
    assert db.execute("SELECT COUNT(*) FROM motor_instance").fetchone()[0] == 1


def test_motor_manager_save_has_distinct_create_and_update_paths():
    source = UI_PATH.read_text(encoding="utf-8")

    assert "if self.current_instance_id is None:" in source
    assert "new_instance_id = self.instance_repo.create(data)" in source
    assert "self.current_instance_id = str(new_instance_id)" in source
    assert "self.instance_repo.update_instance(self.current_instance_id,data)" in source

    # The former dead-end message must not return from the new-instance path.
    assert "新規Instance登録は既存UIの仕様を使用してください。" not in source
