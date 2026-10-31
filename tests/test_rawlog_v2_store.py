import json

import pytest

from raw_log_library.v2_schema import SCHEMA_ID
from raw_log_library.v2_store import RawLogV2Store, RawLogV2StoreError


def _manifest():
    return {
        "schema": SCHEMA_ID,
        "log_id": "MOTOR-000123",
        "measurement_session_id": "session-001",
        "status": "STARTED",
        "started_at": "2026-10-31T10:00:00+09:00",
        "firmware": {"version": "4.00", "build": "test-build"},
        "device": {"type": "MOTOR", "model": "MOTOR_BREAKIN_V3"},
        "measurement_plan": {"id": "WINDING_PWM_SWEEP_0_30"},
    }


def _session_record():
    return {
        "schema": SCHEMA_ID,
        "record_type": "SESSION",
        "log_id": "MOTOR-000123",
        "measurement_session_id": "session-001",
        "record_id": "record-session",
        "sequence": 0,
        "elapsed_time_ms": 0,
        "recorded_at": "2026-10-31T10:00:00+09:00",
        "session_status": "STARTED",
        "device": {"type": "MOTOR", "model": "MOTOR_BREAKIN_V3"},
        "firmware": {"version": "4.00", "build": "test-build"},
        "measurement_plan": {"id": "WINDING_PWM_SWEEP_0_30"},
    }


def test_create_append_finalize_and_read_package(tmp_path):
    store = RawLogV2Store(tmp_path)
    package = store.create(_manifest())
    store.append(_session_record())

    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["record_count"] == 1
    assert manifest["record_type_counts"] == {"SESSION": 1}

    store.finalize(
        "COMPLETE",
        "2026-10-31T10:05:10+09:00",
        reason=None,
    )
    records = store.read_records("MOTOR-000123")
    assert len(records) == 1
    assert records[0]["record_type"] == "SESSION"


def test_store_rejects_duplicate_log_id_without_overwrite(tmp_path):
    store = RawLogV2Store(tmp_path)
    store.create(_manifest())
    with pytest.raises(FileExistsError):
        RawLogV2Store(tmp_path).create(_manifest())


def test_store_rejects_record_from_another_session(tmp_path):
    store = RawLogV2Store(tmp_path)
    store.create(_manifest())
    record = _session_record()
    record["measurement_session_id"] = "other-session"
    with pytest.raises(RawLogV2StoreError, match="measurement_session_id"):
        store.append(record)


def test_store_rejects_duplicate_record_id(tmp_path):
    store = RawLogV2Store(tmp_path)
    store.create(_manifest())
    store.append(_session_record())
    duplicate = dict(_session_record())
    duplicate["sequence"] = 1
    with pytest.raises(RawLogV2StoreError, match="duplicate record_id"):
        store.append(duplicate)


def test_store_requires_strictly_increasing_sequence(tmp_path):
    store = RawLogV2Store(tmp_path)
    store.create(_manifest())
    store.append(_session_record())
    next_record = dict(_session_record())
    next_record.update({"record_id": "record-session-2", "sequence": 0})
    with pytest.raises(RawLogV2StoreError, match="sequence must increase"):
        store.append(next_record)


def test_store_rejects_v1_or_unknown_schema(tmp_path):
    store = RawLogV2Store(tmp_path)
    manifest = _manifest()
    manifest["schema"] = "mini4wd.rawlog.v1"
    with pytest.raises(RawLogV2StoreError, match="schema mismatch"):
        store.create(manifest)
