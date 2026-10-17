import pytest

from controllers.breakin_controller import BreakinController
from controllers.recipe import BreakinPhase
from controllers.motor_benchmark import STANDARD_3V30S, run_benchmark


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
