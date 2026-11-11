from datetime import datetime, timezone

import pytest

from communication.protocol import CSV_FIELDS
from controllers.winding_pwm_sweep_controller import WindingPwmSweepController
from raw_log_library.manager import RawLog, RawLogLibrary
from raw_log_library.v2_schema import RawLogV2ValidationError, SCHEMA_ID, validate_record
from raw_log_library.v2_store import RawLogV2Store


def base(record_type):
    return {
        "schema": SCHEMA_ID,
        "record_type": record_type,
        "log_id": "MOTOR-000123",
        "measurement_session_id": "session-001",
        "record_id": "record-0001",
        "sequence": 0,
        "elapsed_time_ms": 0,
        "recorded_at": "2026-11-11T12:00:00+00:00",
    }


def test_v2_measurement_accepts_wire_capture_without_data26_fields():
    record = base("MEASUREMENT")
    record.update({
        "device_model": "MOTOR_BREAKIN_V3",
        "instance_id": "DEVICE-001",
        "state": "MEASURE",
        "direction": "FWD",
        "pwm": 4,
        "firmware_elapsed_time_ms": 1234,
        "raw_wire_line": "DATA,original,wire,line",
    })
    validate_record(record)


@pytest.mark.parametrize("field", [
    "raw_acs1", "raw_acs2", "current1_a", "current2_a",
    "voltage1_v", "voltage2_v", "motor_voltage_v", "current_avg_a",
    "power_w", "brush_peak_current_a", "raw_magnetic", "motor_temperature_c",
])
def test_v2_measurement_rejects_legacy_data26_derived_fields(field):
    record = base("MEASUREMENT")
    record.update({
        "device_model": "MOTOR_BREAKIN_V3",
        "instance_id": "DEVICE-001",
        "state": "MEASURE",
        "direction": "FWD",
        "pwm": 4,
        "firmware_elapsed_time_ms": 1234,
        "raw_wire_line": "DATA,original,wire,line",
        field: 0.0,
    })
    with pytest.raises(RawLogV2ValidationError, match="legacy DATA-derived"):
        validate_record(record)


@pytest.mark.parametrize("channel", ["A0", "A1", "A4", "A5"])
def test_adc_samples_preserve_each_channel_and_timestamp(channel):
    record = base("ADC_SAMPLE")
    record.update({
        "channel": channel,
        "adc_raw": 512,
        "timestamp_us": 123456,
        "acquisition_sequence": 7,
        "phase": "WINDING",
        "direction": "FWD",
        "pwm": 4,
        "run_state": "MEASURE",
    })
    validate_record(record)


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class FakeDevice:
    def __init__(self):
        self.connected = True
        self.identity_verified = True
        self.device_info = {
            "TYPE": "MOTOR",
            "MODEL": "MOTOR_BREAKIN_V3",
            "FW": "4.00",
            "BUILD": "host-test",
            "ID": "DEVICE-001",
        }
        self.device_reboot_detected = False
        self.raw_log = ""
        self.commands = []

    def arm(self):
        self.commands.append("ARM")
        return True

    def forward(self):
        self.commands.append("FWD")
        return True

    def set_pwm(self, pwm):
        self.commands.append(f"PWM={pwm}")
        return True

    def read_measurement(self):
        return None

    def stop_breakin(self):
        self.commands.extend(["PWM=0", "STOP"])
        return "STOP"

    def emergency_stop(self):
        self.commands.append("EMERGENCY_STOP")
        self.connected = False
        return {"pwm_zero": True, "stop_command": True}

    def push(self, line):
        self.raw_log += line + "\n"


def make_data_line():
    values = {
        "record_type": "DATA",
        "device_model": "MOTOR_BREAKIN_V3",
        "instance_id": "DEVICE-001",
        "elapsed_time": "100",
        "raw_acs1": "512",
        "raw_acs2": "510",
        "current1": "0.01",
        "current2": "0.02",
        "voltage1": "3.0",
        "voltage2": "0.1",
        "motor_voltage": "2.9",
        "pwm": "0",
        "direction": "FWD",
        "state": "MEASURE",
        "current_avg": "0.01",
        "power": "0.029",
        "current_ripple": "0.001",
        "voltage_ripple": "0.002",
        "peak_power": "0.03",
        "peak_current": "0.011",
        "peak_voltage": "3.0",
        "peak_pwm": "0",
        "brush_peak_current": "0.02",
        "raw_magnetic": "500",
        "magnetic_level": "0.5",
        "motor_temperature": "25.0",
    }
    return ",".join(values[name] for name in CSV_FIELDS)


def test_controller_keeps_data26_line_uninterpreted_and_adc_as_individual_samples(tmp_path):
    clock = FakeClock()
    device = FakeDevice()
    store = RawLogV2Store(tmp_path / "v2")
    controller = WindingPwmSweepController(
        device,
        store,
        monotonic=clock,
        wall_clock=lambda: datetime(2026, 11, 11, 12, 0, tzinfo=timezone.utc),
    )
    assert controller.start(
        log_id="MOTOR-000123",
        measurement_session_id="session-001",
        motor_instance_id="42",
    )

    raw_data = make_data_line()
    raw_a0 = "AUX,2,fw-session,7,WINDING,FWD,0,MEASURE,A0,514,123456"
    raw_a1 = "AUX,2,fw-session,8,BRUSH,FWD,0,MEASURE,A1,516,123499"
    device.push(raw_data)
    device.push(raw_a0)
    device.push(raw_a1)
    controller.tick()

    records = store.read_records("MOTOR-000123")
    measurement = next(item for item in records if item["record_type"] == "MEASUREMENT")
    assert measurement["raw_wire_line"] == raw_data
    assert measurement["instance_id"] == "DEVICE-001"
    assert not any(key in measurement for key in (
        "current1_a", "current2_a", "current_avg_a", "power_w",
        "brush_peak_current_a", "motor_temperature_c",
    ))

    samples = [item for item in records if item["record_type"] == "ADC_SAMPLE"]
    assert [(item["channel"], item["adc_raw"], item["timestamp_us"]) for item in samples] == [
        ("A0", 514, 123456),
        ("A1", 516, 123499),
    ]
    assert samples[0]["record_id"] != samples[1]["record_id"]
    assert samples[0]["acquisition_sequence"] != samples[1]["acquisition_sequence"]


def test_rawlog_library_allocates_id_and_indexes_v2_reference(tmp_path):
    library = RawLogLibrary(tmp_path / "raw_logs")
    record = RawLog(
        device_type="MOTOR",
        device_model="MOTOR_BREAKIN_V3",
        firmware_version="4.00",
        device_instance_id="DEVICE-001",
        motor_id="42",
        measurement_session_id="session-001",
    )
    path = library.register_v2_reference(record)
    assert record.log_id == "MOTOR-000001"
    saved, raw_path, metadata_path = library.get(record.log_id)
    assert saved.motor_id == "42"
    assert saved.measurement_session_id == "session-001"
    assert saved.source_reference == "raw_logs_v2/MOTOR-000001/manifest.json"
    assert path == raw_path
    assert metadata_path.exists()
