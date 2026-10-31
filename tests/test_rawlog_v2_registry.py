import json

import pytest

from raw_log_library.v2_registry import RawLogV2Registry, RawLogV2RegistryError
from raw_log_library.v2_store import RawLogV2Store
from raw_log_library.v2_schema import SCHEMA_ID


def _manifest(session="session-001"):
    return {
        "schema": SCHEMA_ID,
        "measurement_session_id": session,
        "status": "STARTED",
        "started_at": "2026-11-01T10:00:00+09:00",
        "device": {"type": "MOTOR", "model": "MOTOR_BREAKIN_V3"},
        "firmware": {"version": "4.00", "build": "test"},
        "measurement_plan": {"id": "WINDING_PWM_SWEEP_0_30"},
    }


def test_v2_registry_allocates_ids_and_creates_v2_packages_only(tmp_path):
    registry = RawLogV2Registry(tmp_path)
    store = RawLogV2Store(tmp_path)

    first = registry.create_package(store, _manifest(), motor_instance_id="000007")
    second = registry.create_package(
        RawLogV2Store(tmp_path), _manifest("session-002"), motor_instance_id="000008"
    )

    assert first.name == "MOTOR-000001"
    assert second.name == "MOTOR-000002"
    assert (first / "manifest.json").is_file()
    assert (first / "records.jsonl").is_file()
    assert not (tmp_path / "index.csv").exists()
    assert not (tmp_path / "MOTOR-000001.log").exists()

    manifest = json.loads((first / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["motor_instance_id"] == "000007"


def test_registry_lists_all_packages_and_keeps_session_association(tmp_path):
    registry = RawLogV2Registry(tmp_path)
    store = RawLogV2Store(tmp_path)
    registry.create_package(store, _manifest(), motor_instance_id="000007")

    items = registry.discover_packages()
    assert len(items) == 1
    assert items[0]["log_id"] == "MOTOR-000001"
    assert items[0]["measurement_session_id"] == "session-001"
    assert items[0]["motor_instance_id"] == "000007"


def test_only_management_fields_can_be_changed(tmp_path):
    registry = RawLogV2Registry(tmp_path)
    store = RawLogV2Store(tmp_path)
    registry.create_package(store, _manifest(), motor_instance_id="000007")

    registry.update_management(
        "MOTOR-000001",
        motor_instance_id="000009",
        instance_visible=False,
        history_registered=True,
        note="inspection note",
    )
    item = registry.get("MOTOR-000001")
    assert item["motor_instance_id"] == "000009"
    assert item["instance_visible"] is False
    assert item["history_registered"] is True
    assert item["note"] == "inspection note"

    with pytest.raises(RawLogV2RegistryError, match="immutable"):
        registry.update_management("MOTOR-000001", schema="tampered")


def test_existing_v2_package_id_is_never_reused(tmp_path):
    registry = RawLogV2Registry(tmp_path)
    store = RawLogV2Store(tmp_path)
    (tmp_path / "MOTOR-000001").mkdir()

    package = registry.create_package(store, _manifest(), motor_instance_id="000007")
    assert package.name == "MOTOR-000002"


def test_registry_rejects_unknown_log_for_management_update(tmp_path):
    registry = RawLogV2Registry(tmp_path)
    with pytest.raises(RawLogV2RegistryError, match="unknown"):
        registry.update_management("MOTOR-000001", note="x")


def test_registry_recovers_management_entry_for_orphaned_v2_package(tmp_path):
    registry = RawLogV2Registry(tmp_path)
    store = RawLogV2Store(tmp_path)
    package = store.create({**_manifest(), "log_id": "MOTOR-000001", "motor_instance_id": "000007"})
    (package / "records.jsonl").touch(exist_ok=True)

    registry.update_management("MOTOR-000001", note="recovered")
    recovered = registry.get("MOTOR-000001")
    assert recovered["motor_instance_id"] == "000007"
    assert recovered["note"] == "recovered"


def test_registry_rejects_store_with_different_root(tmp_path):
    registry = RawLogV2Registry(tmp_path / "registry")
    store = RawLogV2Store(tmp_path / "other")
    with pytest.raises(RawLogV2RegistryError, match="root must match"):
        registry.create_package(store, _manifest(), motor_instance_id="000007")
