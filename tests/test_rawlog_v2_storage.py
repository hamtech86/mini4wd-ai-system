from types import SimpleNamespace

from communication.rawlog_v2_aux import parse_aux_line
from controllers.local_raw_log_breakin_controller import LocalRawLogBreakinController
from raw_log_library import RawLog, RawLogLibrary


class AuxSerial:
    def __init__(self):
        self.raw_log = "INFO,TYPE=MOTOR,MODEL=MOTOR_BREAKIN_V3,FW=3.03\nDATA," + ",".join(["0"] * 25) + "\n"
        self.records = [
            parse_aux_line("AUX,2,session-1,1,WINDING,FWD,0,MEASURE,A0,512,1000"),
            parse_aux_line("AUX,2,session-1,2,WINDING,FWD,0,MEASURE,A4,600,1010"),
        ]
        self.errors = []

    def drain_aux_records(self):
        records, self.records = self.records, []
        return records

    def drain_aux_parse_errors(self):
        errors, self.errors = self.errors, []
        return errors


def test_v1_raw_body_is_immutable_and_v2_aux_is_additive(tmp_path):
    library = RawLogLibrary(tmp_path)
    body = "INFO,TYPE=MOTOR,MODEL=MOTOR_BREAKIN_V3,FW=3.03\r\nDATA," + ",".join(["0"] * 25) + "\r\n"
    record = RawLog(device_type="MOTOR", motor_id="7", device_instance_id="7")
    raw_path = library.register(record, body)
    before = raw_path.read_bytes()

    aux = [
        parse_aux_line("AUX,2,session-1,1,WINDING,FWD,0,MEASURE,A0,512,1000"),
        parse_aux_line("AUX,2,session-1,2,WINDING,FWD,0,MEASURE,A4,600,1010"),
    ]
    result = library.register_v2_aux(record.log_id, aux, [])

    assert raw_path.read_bytes() == before
    manifest = library.read_v2_manifest(record.log_id)
    assert manifest["schema"] == "mini4wd.rawlog.v2"
    assert manifest["raw_body"] == raw_path.name
    assert manifest["aux_record_count"] == 2
    assert manifest["aux_session_ids"] == ["session-1"]
    stored = library.read_v2_aux(record.log_id)
    assert [item["channel"] for item in stored] == ["A0", "A4"]
    assert [item["sample_id"] for item in stored] == [
        "session-1:1:A0", "session-1:2:A4"
    ]
    assert stored[0]["raw_line"].startswith("AUX,2,session-1,1")
    assert result["aux_path"].endswith(".aux.jsonl")


def test_legacy_v1_log_is_not_reclassified_without_aux(tmp_path):
    library = RawLogLibrary(tmp_path)
    record = RawLog(device_type="MOTOR", motor_id="8")
    raw_path = library.register(record, "DATA," + ",".join(["0"] * 25) + "\n")

    assert library.register_v2_aux(record.log_id, [], []) is None
    assert library.read_v2_manifest(record.log_id) is None
    assert raw_path.read_text(encoding="utf-8") == "DATA," + ",".join(["0"] * 25) + "\n"


def test_invalid_aux_diagnostics_are_manifested_without_fabricated_samples(tmp_path):
    library = RawLogLibrary(tmp_path)
    record = RawLog(device_type="MOTOR", motor_id="9")
    library.register(record, "DATA," + ",".join(["0"] * 25) + "\n")
    errors = [{"raw_line": "AUX,2,bad", "error": "field count mismatch"}]

    library.register_v2_aux(record.log_id, [], errors)

    manifest = library.read_v2_manifest(record.log_id)
    assert manifest["aux_record_count"] == 0
    assert manifest["aux_records"] is None
    assert manifest["aux_parse_errors"] == errors
    assert library.read_v2_aux(record.log_id) == []


def test_local_raw_log_controller_attaches_aux_sidecar(tmp_path):
    serial = AuxSerial()
    library = RawLogLibrary(tmp_path)
    controller = LocalRawLogBreakinController(
        serial_controller=serial,
        raw_log_library=library,
    )
    controller.active_instance_id = "7"
    controller.active_recipe_name = "A0_TEST"
    controller.session = SimpleNamespace(session_id="session-1", firmware_version="3.03")

    record = controller._register_raw_log(serial.raw_log)

    assert record.log_id == "MOTOR-000001"
    manifest = library.read_v2_manifest(record.log_id)
    assert manifest["aux_record_count"] == 2
    assert manifest["measurement_session_id"] == "session-1"
    assert manifest["aux_session_ids"] == ["session-1"]
    assert [row["channel"] for row in library.read_v2_aux(record.log_id)] == ["A0", "A4"]
    assert serial.records == []
    assert serial.errors == []


def test_derived_records_keep_formula_version_inputs_and_validity(tmp_path):
    library = RawLogLibrary(tmp_path)
    record = RawLog(device_type="MOTOR", motor_id="10")
    library.register(record, "DATA," + ",".join(["0"] * 25) + "\n")
    aux = [parse_aux_line("AUX,2,session-1,1,WINDING,FWD,0,MEASURE,A0,512,1000")]
    library.register_v2_aux(record.log_id, aux, [])
    derived = [{
        "metric": "winding_resistance",
        "algorithm_id": "winding_resistance_pairing",
        "algorithm_version": "0.1.0",
        "input_sample_ids": ["session-1:1:A0", "session-1:2:A4"],
        "value": 0.42,
        "unit": "ohm",
        "valid": True,
        "invalid_reason": None,
    }]

    path = library.register_v2_derived(record.log_id, derived)

    assert path.endswith(".derived.jsonl")
    saved = library.read_v2_derived(record.log_id)
    assert saved[0]["metric"] == "winding_resistance"
    assert saved[0]["algorithm_version"] == "0.1.0"
    assert saved[0]["input_sample_ids"] == derived[0]["input_sample_ids"]
    manifest = library.read_v2_manifest(record.log_id)
    assert manifest["derived_status"] == "AVAILABLE"
    assert manifest["derived_record_count"] == 1


def test_invalid_derived_record_requires_reason_and_does_not_write(tmp_path):
    library = RawLogLibrary(tmp_path)
    record = RawLog(device_type="MOTOR", motor_id="11")
    library.register(record, "DATA," + ",".join(["0"] * 25) + "\n")
    invalid = [{
        "metric": "brush_stability",
        "algorithm_id": "brush_eval",
        "algorithm_version": "0.1.0",
        "input_sample_ids": ["session-1:5:A1"],
        "value": None,
        "unit": "ratio",
        "valid": False,
        "invalid_reason": "",
    }]

    import pytest
    with pytest.raises(ValueError, match="invalid_reason"):
        library.register_v2_derived(record.log_id, invalid)

    assert library.read_v2_manifest(record.log_id) is None
    assert library.read_v2_derived(record.log_id) == []



def test_duplicate_aux_sample_identity_is_rejected(tmp_path):
    import pytest

    library = RawLogLibrary(tmp_path)
    record = RawLog(device_type="MOTOR", motor_id="12")
    library.register(record, "raw body\\n")
    duplicate_samples = [
        parse_aux_line("AUX,2,session-1,1,WINDING,FWD,0,MEASURE,A0,512,1000"),
        parse_aux_line("AUX,2,session-1,1,WINDING,FWD,0,MEASURE,A0,513,1010"),
    ]

    with pytest.raises(ValueError, match="duplicate AUX sample_id"):
        library.register_v2_aux(record.log_id, duplicate_samples, [])

    assert library.read_v2_manifest(record.log_id) is None
