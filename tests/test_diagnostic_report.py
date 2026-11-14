import json

import pytest

from diagnostic_report import DiagnosticReportError, DiagnosticReportService
from raw_log_library import RawLog, RawLogLibrary


def test_anonymous_battery_ch1_ch2_bundle_preserves_original_crlf(tmp_path):
    library = RawLogLibrary(tmp_path / "raw")
    ch1 = RawLog(device_type="BATTERY", device_model="BATTERY_5A", channel="CH1")
    ch2 = RawLog(device_type="BATTERY", device_model="BATTERY_5A", channel="CH2")
    library.register(ch1, "DATA,1\r\nERROR,LOW\r\n")
    library.register(ch2, "DATA,2\nCOMPLETE\n")
    service = DiagnosticReportService(library, tmp_path / "reports")

    bundle = service.create_local_bundle(
        "BATTERY", [ch1.log_id, ch2.log_id],
        error_code="LOW_VOLTAGE", error_message="CH1 cutoff",
        context={"anonymous": True, "instance_id": None},
        run_id="battery-anonymous-001",
    )

    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["device_type"] == "BATTERY"
    assert manifest["context"]["anonymous"] is True
    assert [x["channel"] for x in manifest["selected_raw_logs"]] == ["CH1", "CH2"]
    assert (bundle / "raw_logs" / f"{ch1.log_id}.log").read_bytes() == b"DATA,1\r\nERROR,LOW\r\n"
    assert (bundle / "raw_logs" / f"{ch2.log_id}.log").read_bytes() == b"DATA,2\nCOMPLETE\n"
    assert library.read_raw(ch1.log_id) == "DATA,1\r\nERROR,LOW\r\n"
    assert library.read_raw(ch2.log_id) == "DATA,2\nCOMPLETE\n"


def test_battery_channel_can_be_selected_individually(tmp_path):
    library = RawLogLibrary(tmp_path / "raw")
    ch1 = RawLog(device_type="BATTERY", channel="CH1")
    ch2 = RawLog(device_type="BATTERY", channel="CH2")
    library.register(ch1, "CH1\n")
    library.register(ch2, "CH2\n")
    service = DiagnosticReportService(library, tmp_path / "reports")
    bundle = service.create_local_bundle("BATTERY", [ch2.log_id], run_id="ch2-only")
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert [row["channel"] for row in manifest["selected_raw_logs"]] == ["CH2"]
    assert (bundle / "raw_logs" / f"{ch2.log_id}.log").read_bytes() == b"CH2\n"


def test_motor_report_does_not_require_instance(tmp_path):
    library = RawLogLibrary(tmp_path / "raw")
    motor = RawLog(device_type="MOTOR", motor_id=None, device_instance_id=None)
    library.register(motor, "time_ms,current\n0,0.1\n")
    service = DiagnosticReportService(library, tmp_path / "reports")
    bundle = service.create_local_bundle("MOTOR", [motor.log_id], run_id="motor-no-instance")
    manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["selected_raw_logs"][0]["device_instance_id"] is None
    assert (bundle / "raw_logs" / f"{motor.log_id}.log").read_bytes() == b"time_ms,current\n0,0.1\n"


def test_device_type_mismatch_is_rejected(tmp_path):
    library = RawLogLibrary(tmp_path / "raw")
    motor = RawLog(device_type="MOTOR")
    library.register(motor, "RAW\n")
    service = DiagnosticReportService(library, tmp_path / "reports")
    with pytest.raises(ValueError, match="not a BATTERY"):
        service.create_local_bundle("BATTERY", [motor.log_id], run_id="wrong-type")


def test_upload_without_token_keeps_local_bundle(tmp_path):
    library = RawLogLibrary(tmp_path / "raw")
    battery = RawLog(device_type="BATTERY", channel="CH1")
    library.register(battery, "RAW\r\n")
    service = DiagnosticReportService(library, tmp_path / "reports")
    bundle = service.create_local_bundle("BATTERY", [battery.log_id], run_id="no-token")
    with pytest.raises(DiagnosticReportError) as error:
        service.upload_bundle(bundle)
    assert error.value.local_bundle == bundle
    assert (bundle / "manifest.json").is_file()
    assert (bundle / "raw_logs" / f"{battery.log_id}.log").read_bytes() == b"RAW\r\n"
    assert not (bundle / "upload_status.json").exists()


def test_duplicate_run_id_never_overwrites_existing_bundle(tmp_path):
    library = RawLogLibrary(tmp_path / "raw")
    battery = RawLog(device_type="BATTERY", channel="CH1")
    library.register(battery, "RAW\n")
    service = DiagnosticReportService(library, tmp_path / "reports")
    service.create_local_bundle("BATTERY", [battery.log_id], run_id="same-id")
    with pytest.raises(FileExistsError):
        service.create_local_bundle("BATTERY", [battery.log_id], run_id="same-id")



def test_identical_remote_blob_is_detected_for_safe_retry(tmp_path, monkeypatch):
    import hashlib
    from types import SimpleNamespace
    import diagnostic_report

    content = b"same content\r\n"
    blob_sha = hashlib.sha1(
        b"blob " + str(len(content)).encode("ascii") + b"\\0" + content
    ).hexdigest()

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self):
            return json.dumps({"sha": blob_sha}).encode("utf-8")

    monkeypatch.setattr(diagnostic_report.urllib.request, "urlopen", lambda *args, **kwargs: Response())
    service = DiagnosticReportService(
        RawLogLibrary(tmp_path / "raw"), tmp_path / "reports", token="test-token"
    )
    result = service._put_new_file("diagnostic-reports/battery/run/raw.log", content, "test")
    assert result["status"] == "ALREADY_PRESENT_IDENTICAL"


def test_upload_status_file_is_not_included_on_retry(tmp_path, monkeypatch):
    library = RawLogLibrary(tmp_path / "raw")
    battery = RawLog(device_type="BATTERY", channel="CH1")
    library.register(battery, "RAW\\n")
    service = DiagnosticReportService(
        library, tmp_path / "reports", token="test-token"
    )
    bundle = service.create_local_bundle("BATTERY", [battery.log_id], run_id="status-excluded")
    uploaded_paths = []

    def fake_put(path, content, message):
        uploaded_paths.append(path)
        return {"status": "created"}

    monkeypatch.setattr(service, "_put_new_file", fake_put)
    service.upload_bundle(bundle)
    first_count = len(uploaded_paths)
    assert first_count == 2  # manifest + explicitly selected RawLog
    assert (bundle / "upload_status.json").is_file()

    service.upload_bundle(bundle)
    assert len(uploaded_paths) == first_count * 2
    assert all(not path.endswith("upload_status.json") for path in uploaded_paths)
