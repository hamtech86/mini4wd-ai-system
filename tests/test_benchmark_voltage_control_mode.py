from controllers.motor_benchmark import (
    FULL_PACKAGE,
    INPUT,
    STANDARD_3V30S,
    TERMINAL,
    _benchmark_voltage_control,
)
from controllers.recipe import BreakinPhase


class SerialStub:
    def __init__(self):
        self.commands = []

    def set_pwm(self, value):
        self.commands.append(("PWM", value))


class ControllerStub:
    VOLTAGE_KP = 20.0

    def __init__(self, mode):
        self.serial = SerialStub()
        self.current_pwm = 80
        self.benchmark_voltage_control_mode = mode

    @staticmethod
    def _value(measurement, name, default=0.0):
        return measurement.get(name, default)


def phase(direction):
    return BreakinPhase(
        name="TEST", duration_sec=1, pwm=80, direction=direction,
        control="VOLTAGE", target_voltage=3.0, pwm_min=35, pwm_max=120,
    )


def test_input_mode_selects_physical_input_by_direction():
    fwd = ControllerStub(INPUT)
    measurement = {"voltage1": 2.8, "voltage2": 1.0, "motor_voltage": 1.8, "direction": "FWD"}
    _benchmark_voltage_control(fwd, phase("FWD"), measurement)
    assert fwd.current_pwm == 84

    rev = ControllerStub(INPUT)
    measurement = {"voltage1": 1.0, "voltage2": 2.8, "motor_voltage": -1.8, "direction": "REV"}
    _benchmark_voltage_control(rev, phase("REV"), measurement)
    assert rev.current_pwm == 84


def test_terminal_mode_uses_directional_terminal_voltage():
    fwd = ControllerStub(TERMINAL)
    _benchmark_voltage_control(
        fwd, phase("FWD"),
        {"voltage1": 3.0, "voltage2": 0.2, "motor_voltage": 2.8},
    )
    assert fwd.current_pwm == 84

    rev = ControllerStub(TERMINAL)
    _benchmark_voltage_control(
        rev, phase("REV"),
        {"voltage1": 0.2, "voltage2": 3.0, "motor_voltage": -2.8},
    )
    assert rev.current_pwm == 84


def test_benchmark_types_remain_unchanged():
    assert STANDARD_3V30S == "STANDARD_3V30S"
    assert FULL_PACKAGE == "FULL_PACKAGE"
