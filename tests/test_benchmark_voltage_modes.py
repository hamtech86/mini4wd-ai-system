import pytest

from controllers.breakin_controller import BreakinController
from controllers.local_raw_log_breakin_controller import LocalRawLogBreakinController
from controllers.recipe import BreakinPhase
import controllers.motor_benchmark as benchmark_module
from controllers.motor_benchmark import STANDARD_3V30S, _begin, run_benchmark


class MockSerial:
    def __init__(self):
        self.commands = []

    def set_pwm(self, pwm):
        self.commands.append(("PWM", pwm))

    def forward(self):
        self.commands.append("FWD")

    def reverse(self):
        self.commands.append("REV")

    def stop_breakin(self):
        self.commands.append("STOP")


def make_controller(mode):
    serial = MockSerial()
    controller = BreakinController(serial_controller=serial)
    controller.current_pwm = 80
    controller.benchmark_voltage_control_mode = mode
    return controller, serial


@pytest.mark.parametrize(
    ("direction", "measurement"),
    [
        ("FWD", {"voltage1": 2.0, "voltage2": 4.0, "motor_voltage": 2.0}),
        ("REV", {"voltage1": 4.0, "voltage2": 2.0, "motor_voltage": -2.0}),
    ],
)
def test_input_mode_uses_direction_specific_input_voltage(direction, measurement):
    controller, serial = make_controller("INPUT")
    phase = BreakinPhase("test", 1, 80, direction, "VOLTAGE", 3.0, pwm_min=0, pwm_max=255)
    controller._voltage_control(phase, measurement)
    assert controller.current_pwm == 100
    assert serial.commands == [("PWM", 100)]


@pytest.mark.parametrize(
    ("direction", "measurement"),
    [
        ("FWD", {"motor_voltage": 2.0, "voltage1": 4.0, "voltage2": 0.5}),
        ("REV", {"motor_voltage": -2.0, "voltage1": 0.5, "voltage2": 4.0}),
    ],
)
def test_terminal_mode_uses_signed_motor_voltage_in_drive_direction(direction, measurement):
    controller, serial = make_controller("TERMINAL")
    phase = BreakinPhase("test", 1, 80, direction, "VOLTAGE", 3.0, pwm_min=0, pwm_max=255)
    controller._voltage_control(phase, measurement)
    assert controller.current_pwm == 100
    assert serial.commands == [("PWM", 100)]


def test_input_mode_does_not_use_opposite_terminal_for_feedback():
    controller, serial = make_controller("INPUT")
    phase = BreakinPhase("test", 1, 80, "FWD", "VOLTAGE", 3.0, pwm_min=0, pwm_max=255)
    controller._voltage_control(phase, {"voltage1": 3.0, "voltage2": 0.5, "motor_voltage": 0.5})
    assert controller.current_pwm == 80
    assert serial.commands == []


def test_benchmark_rejects_unknown_voltage_control_mode_before_driving():
    controller, serial = make_controller("TERMINAL")
    with pytest.raises(ValueError, match="Unsupported voltage control mode"):
        run_benchmark(controller, STANDARD_3V30S, voltage_control_mode="SILENT_FALLBACK")
    assert serial.commands == []


def test_input_mode_does_not_fall_back_to_motor_voltage_when_input_is_missing():
    controller, serial = make_controller("INPUT")
    phase = BreakinPhase("test", 1, 80, "FWD", "VOLTAGE", 3.0, pwm_min=0, pwm_max=255)
    controller._voltage_control(phase, {"motor_voltage": 1.0, "voltage2": 4.0})
    assert controller.current_pwm == 80
    assert serial.commands == []


def test_non_finite_voltage_sample_does_not_change_pwm():
    controller, serial = make_controller("INPUT")
    phase = BreakinPhase("test", 1, 80, "FWD", "VOLTAGE", 3.0, pwm_min=0, pwm_max=255)
    controller._voltage_control(phase, {"voltage1": float("nan"), "motor_voltage": 1.0})
    assert controller.current_pwm == 80
    assert serial.commands == []


def test_benchmark_voltage_mode_is_recorded_in_session_metadata():
    class SessionManager:
        def start(self, *args, **kwargs):
            from types import SimpleNamespace
            return SimpleNamespace(notes='', benchmark_type=None, purpose=None)

    controller, _ = make_controller('INPUT')
    controller.session_manager = SessionManager()
    _begin(controller, STANDARD_3V30S, instance_id=42)
    assert controller.session.voltage_control_mode == 'INPUT'
    assert 'voltage_control_mode=INPUT' in controller.session.notes


def test_standard_benchmark_finishes_and_resets_voltage_mode(monkeypatch):
    controller, serial = make_controller("TERMINAL")
    monkeypatch.setattr(benchmark_module, "_prepare_3v", lambda *args, **kwargs: True)
    monkeypatch.setattr(benchmark_module, "_timed_voltage", lambda *args, **kwargs: True)
    result = run_benchmark(controller, STANDARD_3V30S, voltage_control_mode="INPUT")
    assert result == []
    assert controller.running is False
    assert controller.benchmark_voltage_control_mode == "TERMINAL"
    assert "FWD" in serial.commands
    assert "STOP" in serial.commands


def test_benchmark_preparation_abort_requests_stop_and_resets_mode(monkeypatch):
    controller, serial = make_controller("TERMINAL")
    monkeypatch.setattr(benchmark_module, "_prepare_3v", lambda *args, **kwargs: False)
    with pytest.raises(RuntimeError, match="stopped during preparation"):
        run_benchmark(controller, STANDARD_3V30S, voltage_control_mode="INPUT")
    assert controller.running is False
    assert controller.current_pwm == 0
    assert controller.benchmark_voltage_control_mode == "TERMINAL"
    assert "FWD" in serial.commands
    assert "STOP" in serial.commands


def test_raw_log_sidecar_records_voltage_mode_without_changing_raw_body():
    from types import SimpleNamespace

    class FakeRawLogLibrary:
        def register(self, record, raw_body):
            self.record = record
            self.raw_body = raw_body
            return "/fake/raw-log-path"

    library = FakeRawLogLibrary()
    controller = LocalRawLogBreakinController(
        serial_controller=MockSerial(), raw_log_library=library
    )
    controller.active_instance_id = 42
    controller.session = SimpleNamespace(session_id="session-42", firmware_version="3.00")
    controller.selected_benchmark_type = STANDARD_3V30S
    controller.active_recipe_name = STANDARD_3V30S
    controller.benchmark_type = STANDARD_3V30S
    controller.benchmark_voltage_control_mode = "INPUT"
    body = "DATA,raw,body\\r\\nCAL,raw,calibration\\r\\n"
    controller._register_raw_log(body)
    assert library.record.measurement_condition == STANDARD_3V30S
    assert "voltage_control_mode=INPUT" in library.record.notes
    assert library.raw_body == body
