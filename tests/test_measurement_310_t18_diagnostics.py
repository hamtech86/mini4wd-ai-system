"""Tests for observational T18 persistence timing diagnostics."""

import json

from measurement_310.t18_production_profile import PersistenceProfiler
from raw_log_v2 import RawLogV2Writer


def test_persistence_profiler_measures_rawlog_append_and_fsync_without_skipping(tmp_path):
    root = tmp_path / "rawlog"
    writer = RawLogV2Writer(root)
    session = writer.begin({
        "log_id": "T18-DIAGNOSTIC",
        "measurement_session_id": "diagnostic-session",
        "started_at_utc": "2026-11-07T00:00:00Z",
    })

    profiler = PersistenceProfiler()
    with profiler:
        profiler.current_stage = 7
        session.append_many([{
            "schema_version": "2.0.0",
            "record_type": "SESSION_EVENT",
            "record_id": "diagnostic-record-1",
            "record_seq": 1,
            "log_id": "T18-DIAGNOSTIC",
            "measurement_session_id": "diagnostic-session",
            "recorded_at_utc": "2026-11-07T00:00:01Z",
            "event": "DIAGNOSTIC_TEST",
        }])

    summary = profiler.stage_summary(7)
    assert summary["rawlog_append_many_count"] == 1
    assert summary["fsync_rawlog_records_file_count"] == 1
    assert summary["fsync_rawlog_work_state_file_count"] == 0
    assert summary["fsync_rawlog_directory_count"] == 0

    # The records are durable on every append. The work-state is a bounded
    # checkpoint and is intentionally not rewritten for this first append.
    records = (session.work_dir / "records.jsonl").read_text(encoding="utf-8")
    assert json.loads(records.splitlines()[0])["event"] == "DIAGNOSTIC_TEST"
    durable_checkpoint = json.loads(session.state_path.read_text(encoding="utf-8"))
    assert durable_checkpoint["record_count"] == 0
    assert durable_checkpoint["last_record_seq"] == 0
    assert session.state["record_count"] == 1
    assert session.state["last_record_seq"] == 1


def test_persistence_profiler_restores_patched_functions_after_exit():
    import os
    from raw_log_v2 import storage

    original_fsync = os.fsync
    original_append_many = storage.RawLogV2Session.append_many
    with PersistenceProfiler():
        assert os.fsync is not original_fsync
        assert storage.RawLogV2Session.append_many is not original_append_many
    assert os.fsync is original_fsync
    assert storage.RawLogV2Session.append_many is original_append_many
