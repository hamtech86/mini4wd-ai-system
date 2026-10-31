from datetime import datetime, timezone

from communication.protocol import CSV_FIELDS
from controllers.winding_pwm_sweep_controller import WindingPwmSweepController
from raw_log_library.v2_store import RawLogV2Store


class FakeClock:
    def __init__(self):
        self.value = 100.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class FakeSerialController:
    def __init__(self):
        self.connected = True
        self.identity_verified = True
        self.device_reboot_detected = False
        self.device_info = {
            "TYPE": "MOTOR",
            "MODEL": "MOTOR_BREAKIN_V3",
            "FW": "4.00",
            "BUILD": "winding-test",
            "ID": "000001",
        }
        self.raw_log = ""
        self.commands = []
        self.emergency_stop_count = 0

    def arm(self):
        self.commands.append("ARM")
        return True

    def forward(self):
        self.commands.append("FWD")
        return "FWD"

    def set_pwm(self, pwm):
        self.commands.append(f"PWM={pwm}")
        return f"PWM={pwm}"

    def read_measurement(self):
        return None

    def stop_breakin(self):
        self.commands.extend(["PWM=0", "STOP"])
        return "STOP"

    def emergency_stop(self):
        self.emergency_stop_count += 1
        self.commands.extend(["EMERGENCY_PWM=0", "EMERGENCY_STOP"])
        self.connected = False
        return {"pwm_zero": True, "stop_command": True}

    def push_line(self, line):
        self.raw_log += line + "\n"


def _make_controller(tmp_path, clock=None, device=None):
    clock = clock or FakeClock()
    device = device or FakeSerialController()
    store = RawLogV2Store(tmp_path)
    controller = WindingPwmSweepController(
        device,
        store,
        monotonic=clock,
        wall_clock=lambda: datetime(2026, 10, 31, 10, 0, 0, tzinfo=timezone.utc),
    )
    return controller, store, device, clock


def _start(controller):
    assert controller.start(
        log_id="MOTOR-000123",
        measurement_session_id="session-001",
    )


def _data_line():
    values = {
        "record_type": "DATA",
        "device_model": "MOTOR_BREAKIN_V3",
        "instance_id": "000001",
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
    return ",".join(values[field] for field in CSV_FIELDS)


def test_python_coordinator_runs_pwm_0_to_30_then_stops(tmp_path):
    controller, store, device, clock = _make_controller(tmp_path)
    _start(controller)

    assert controller.stage_index == 0
    assert controller.stage_pwm == 0
    assert device.commands[:3] == ["ARM", "FWD", "PWM=0"]

    for pwm in range(1, 31):
        clock.advance(10.0)
        state = controller.tick()
        assert state["status"] == "RUNNING"
        assert state["stage_index"] == pwm
        assert state["pwm"] == pwm

    clock.advance(10.0)
    state = controller.tick()
    assert state["status"] == "IDLE"
    assert device.commands[-2:] == ["PWM=0", "STOP"]

    records = store.read_records("MOTOR-000123")
    stages = [
        record["details"]["pwm"]
        for record in records
        if record["record_type"] == "EVENT"
        and record["event_type"] == "PWM_STAGE_STARTED"
    ]
    assert stages == list(range(31))


def test_coordinator_retains_full_data_record_and_original_wire_line(tmp_path):
    controller, store, device, clock = _make_controller(tmp_path)
    _start(controller)
    raw_line = _data_line()
    device.push_line(raw_line)
    controller.tick()

    records = store.read_records("MOTOR-000123")
    measurement = next(record for record in records if record["record_type"] == "MEASUREMENT")
    assert measurement["instance_id"] == "000001"
    assert measurement["raw_acs1"] == 512
    assert measurement["brush_peak_current_a"] == 0.02
    assert measurement["motor_temperature_c"] == 25.0
    assert measurement["raw_wire_line"] == raw_line


def test_coordinator_retains_individual_aux_adc_timestamp(tmp_path):
    controller, store, device, clock = _make_controller(tmp_path)
    _start(controller)
    raw_line = "AUX,2,fw_session_1,7,WINDING,FWD,0,MEASURE,A0,514,123456"
    device.push_line(raw_line)
    controller.tick()

    records = store.read_records("MOTOR-000123")
    sample = next(record for record in records if record["record_type"] == "ADC_SAMPLE")
    assert sample["channel"] == "A0"
    assert sample["adc_raw"] == 514
    assert sample["timestamp_us"] == 123456
    assert sample["acquisition_sequence"] == 7
    assert sample["raw_wire_line"] == raw_line


def test_rotation_observation_is_saved_as_an_event(tmp_path):
    controller, store, device, clock = _make_controller(tmp_path)
    _start(controller)
    controller.record_rotation_observation("ROTATION", "visible movement")
    records = store.read_records("MOTOR-000123")
    observation = next(
        record for record in records
        if record["record_type"] == "EVENT"
        and record["event_type"] == "ROTATION_OBSERVATION"
    )
    assert observation["details"]["label"] == "ROTATION"
    assert observation["details"]["pwm"] == 0


def test_connection_loss_emergency_stops_and_marks_package_faulted(tmp_path):
    controller, store, device, clock = _make_controller(tmp_path)
    _start(controller)
    device.connected = False

    controller.tick()

    import json
    manifest = json.loads((tmp_path / "MOTOR-000123" / "manifest.json").read_text())
    assert manifest["status"] == "FAULTED"
    assert device.emergency_stop_count == 1


def test_user_stop_marks_package_stopped_not_complete(tmp_path):
    controller, store, device, clock = _make_controller(tmp_path)
    _start(controller)
    assert controller.stop("operator_requested")
    import json
    manifest = json.loads((tmp_path / "MOTOR-000123" / "manifest.json").read_text())
    assert manifest["status"] == "STOPPED"
    assert manifest["final_reason"] == "operator_requested"
