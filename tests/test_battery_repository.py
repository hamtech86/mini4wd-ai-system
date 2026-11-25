import sqlite3

from database.repository.battery_repository import BatteryBenchmarkResultRepository, BatteryInstanceRepository, BatteryModelRepository


def test_battery_model_instance_and_result_repositories():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE measurement_session (session_id TEXT PRIMARY KEY)")

    models = BatteryModelRepository(db)
    models.ensure_schema()
    model = models.get_by_code("NEO_STD")
    assert model is not None

    instances = BatteryInstanceRepository(db)
    instances.ensure_schema()
    instances.create({"instance_id": "BAT-001", "battery_model_id": model["battery_model_id"], "nickname": "test"})
    assert instances.get_by_id("BAT-001")["battery_model_id"] == model["battery_model_id"]

    db.execute("INSERT INTO measurement_session VALUES ('S1')")
    results = BatteryBenchmarkResultRepository(db)
    results.ensure_schema()
    results.save({"session_id": "S1", "instance_id": "BAT-001", "analysis_version": "v1", "measurement_count": 1})
    assert results.get_for_session("S1", "v1")["measurement_count"] == 1


def test_benchmark_repository_is_idempotent_and_conflicts_without_row_factory():
    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE measurement_session (session_id TEXT PRIMARY KEY)")
    db.execute("INSERT INTO measurement_session VALUES ('S1')")
    repository = BatteryBenchmarkResultRepository(db)
    repository.ensure_schema()
    payload = {
        "session_id": "S1", "instance_id": None, "analysis_version": "v1",
        "measurement_count": 2, "avg_voltage": 1.35,
    }
    first_id = repository.save(payload)
    retry_id = repository.save(dict(payload))
    assert retry_id == first_id
    assert db.execute("SELECT COUNT(*) FROM battery_benchmark_result").fetchone()[0] == 1

    changed = dict(payload)
    changed["avg_voltage"] = 1.2
    try:
        repository.save(changed)
    except ValueError as exc:
        assert "conflict" in str(exc).lower()
    else:
        raise AssertionError("different payload must conflict")
    row = db.execute("SELECT result_id,avg_voltage FROM battery_benchmark_result").fetchone()
    assert row == (first_id, 1.35)
