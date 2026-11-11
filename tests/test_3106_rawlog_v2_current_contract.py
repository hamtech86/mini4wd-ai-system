from datetime import datetime, timezone
import json
import sys
import uuid

import pytest
from PyQt5.QtWidgets import QApplication

from ui.winding_sweep_panel import WindingSweepPanel
from measurement_310.evidence_bundle import write_evidence_bundle_manifest
from measurement_310.protocol_v1_session import TransportEvidenceJournal
from measurement_310.transport import PySerialTransport
from raw_log_library.github_export import GitHubRawLogExporter, GitHubRegistrationError
from raw_log_library.manager import RawLog, RawLogLibrary


def _make_library_reference(tmp_path):
    data_root = tmp_path / "data"
    session_id = str(uuid.uuid4())
    library = RawLogLibrary(data_root / "raw_logs")
    record = RawLog(
        device_type="MOTOR",
        device_model="MOTOR_BREAKIN_V3",
        firmware_version=None,
        device_instance_id="42",
        motor_id="42",
        measurement_session_id=session_id,
        acquired_at=datetime.now(timezone.utc).isoformat(),
        measurement_condition="Protocol v2 PWM 0..30",
        notes="binary protocol v2",
    )
    library.register_v2_reference(record)
    return data_root, library, record


def test_rawlog_library_allocates_id_and_indexes_v2_reference(tmp_path):
    data_root, library, record = _make_library_reference(tmp_path)
    saved, raw_path, metadata_path = library.get(record.log_id)

    assert record.log_id == "MOTOR-000001"
    assert saved.device_instance_id == "42"
    assert saved.motor_id == "42"
    assert saved.measurement_session_id == record.measurement_session_id
    assert saved.source_reference == f"raw_logs_v2/{record.log_id}/manifest.json"
    assert raw_path.suffix == ".v2ref"
    assert raw_path.is_file()
    assert metadata_path.is_file()


def test_github_export_verifies_and_uploads_rawlog_and_evidence_bundle(tmp_path):
    data_root, library, record = _make_library_reference(tmp_path)
    package_root = data_root / "raw_logs_v2"
    package_dir = package_root / record.log_id
    package_dir.mkdir(parents=True)
    manifest = {
        "schema_name": "mini4wd.rawlog",
        "schema_version": "2.0.0",
        "log_id": record.log_id,
        "measurement_session_id": record.measurement_session_id,
        "status": "completed",
    }
    (package_dir / "manifest.json").write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    (package_dir / "records.jsonl").write_text("", encoding="utf-8")

    evidence = TransportEvidenceJournal.for_session(package_root, record.measurement_session_id)
    evidence.append(
        "HOST_TEST_EVENT", {"test": True},
        measurement_session_id=record.measurement_session_id,
    )
    write_evidence_bundle_manifest(package_dir, evidence, record.measurement_session_id)

    exporter = GitHubRawLogExporter(library, token="dummy")
    uploaded = []

    def fake_put(path, body, message, *, allow_update):
        uploaded.append((path, body, allow_update))
        return {"commit": {"sha": "test-commit"}}

    exporter._put_file = fake_put
    result = exporter.register(record.log_id)

    paths = [item[0] for item in uploaded]
    base = f"motor/42/{record.log_id}"
    assert result["status"] == "REGISTERED"
    assert f"{base}/manifest.json" in paths
    assert f"{base}/records.jsonl" in paths
    assert f"{base}/transport-evidence-v1.jsonl" in paths
    assert f"{base}/bundle-manifest.json" in paths
    assert f"{base}/metadata.json" in paths
    assert not any(path.endswith(".v2ref") or path.endswith("raw.log") for path in paths)
    assert library.get_github_status(record.log_id)["status"] == "REGISTERED"


def test_github_export_refuses_unrecovered_incomplete_work(tmp_path):
    data_root, library, record = _make_library_reference(tmp_path)
    package_root = data_root / "raw_logs_v2"
    work_dir = package_root / ".work" / record.log_id
    work_dir.mkdir(parents=True)
    (work_dir / "work_state.json").write_text('{"phase":"recording"}\n', encoding="utf-8")
    (work_dir / "records.jsonl").write_text("", encoding="utf-8")

    exporter = GitHubRawLogExporter(library, token="dummy")
    with pytest.raises(GitHubRegistrationError, match="package files are incomplete"):
        exporter.register(record.log_id)


def test_pyserial_transport_waits_for_configured_uno_startup_delay(monkeypatch):
    class FakeSerial:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        def close(self):
            pass

    class FakeSerialModule:
        Serial = FakeSerial

    sleeps = []
    monkeypatch.setitem(sys.modules, "serial", FakeSerialModule())
    monkeypatch.setattr("time.sleep", lambda seconds: sleeps.append(seconds))
    transport = PySerialTransport(
        "/dev/fake-motor", 57600, timeout_s=0.0,
        write_timeout_s=0.10, startup_delay_s=2.0,
    )
    transport.connect()
    assert sleeps == [2.0]
    assert transport._serial is not None
    transport.disconnect()


def test_pyserial_transport_rejects_negative_startup_delay():
    with pytest.raises(ValueError, match="invalid serial configuration"):
        PySerialTransport("/dev/fake-motor", 57600, startup_delay_s=-0.1)



def test_qt_tick_queue_coalesces_pending_worker_ticks(tmp_path):
    app = QApplication.instance() or QApplication([])
    panel = WindingSweepPanel(
        None, tmp_path,
        get_instance_id=lambda: "42",
        get_breakin_controller=lambda: None,
    )
    panel._worker = object()
    queued = []
    panel.tick_requested.connect(lambda: queued.append("tick"))

    panel._queue_tick()
    panel._queue_tick()
    assert queued == ["tick"]
    assert panel._tick_pending is True

    panel._on_progress({
        "state": "RUNNING",
        "stage_index": 0,
        "pwm": 0,
        "elapsed_seconds": 0.1,
    })
    panel._queue_tick()
    assert queued == ["tick", "tick"]

    panel.timer.stop()
    panel.close()
    app.processEvents()
