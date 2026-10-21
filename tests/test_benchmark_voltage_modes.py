"""Regression tests for INPUT versus TERMINAL benchmark feedback."""
from types import SimpleNamespace

from controllers.breakin_controller import BreakinController
from controllers.recipe import BreakinPhase
from controllers.ui_benchmark_presets import BENCHMARK_PRESETS


class FakeSerial:
    def __init__(self):
        self.pwm = []

    def set_pwm(self, value):
        self.pwm.append(value)


def test_four_preset_mapping_is_canonical():
    assert BENCHMARK_PRESETS == {
        "STD-T": ("STANDARD_3V30S", "TERMINAL"),
        "Full-T": ("FULL_PACKAGE", "TERMINAL"),
        "STD-I": ("STANDARD_3V30S", "INPUT"),
        "Full-I": ("FULL_PACKAGE", "INPUT"),
    }


def test_input_mode_uses_directional_input_sensor_not_terminal_voltage():
    serial = FakeSerial()
    controller = BreakinController(serial_controller=serial)
    controller.current_pwm = 100
    controller.benchmark_voltage_control_mode = "INPUT"
    phase = BreakinPhase("TEST", duration_sec=1, pwm=100, direction="FWD",
                         control="VOLTAGE", target_voltage=3.0,
                         pwm_min=0, pwm_max=255)
    measurement = SimpleNamespace(voltage1=2.5, voltage2=2.0, motor_voltage=2.0)

    controller._voltage_control(phase, measurement)

    assert serial.pwm == [110]


def test_input_mode_reverse_uses_voltage2():
    serial = FakeSerial()
    controller = BreakinController(serial_controller=serial)
    controller.current_pwm = 100
    controller.benchmark_voltage_control_mode = "INPUT"
    phase = BreakinPhase("TEST", duration_sec=1, pwm=100, direction="REV",
                         control_mode="VOLTAGE", target_voltage=3.0,
                         pwm_min=0, pwm_max=255)
    measurement = SimpleNamespace(voltage1=2.5, voltage2=2.0, motor_voltage=-2.5)

    controller._voltage_control(phase, measurement)

    assert serial.pwm == [120]


def test_terminal_mode_uses_direction_normalized_motor_voltage():
    serial = FakeSerial()
    controller = BreakinController(serial_controller=serial)
    controller.current_pwm = 100
    controller.benchmark_voltage_control_mode = "TERMINAL"
    phase = BreakinPhase("TEST", duration_sec=1, pwm=100, direction="REV",
                         control_mode="VOLTAGE", target_voltage=3.0,
                         pwm_min=0, pwm_max=255)
    measurement = SimpleNamespace(voltage1=2.5, voltage2=2.0, motor_voltage=-2.5)

    controller._voltage_control(phase, measurement)

    assert serial.pwm == [110]
