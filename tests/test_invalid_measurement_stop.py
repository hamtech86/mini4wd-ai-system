"""Regression tests for the three-consecutive-invalid-sample safety gate."""
import pytest

from controllers.breakin_controller import BreakinController
from controllers.recipe import BreakinPhase


class EmptyMeasurementManager:
    def collect(self):
        return None


class StopTransport:
    def __init__(self):
        self.stop_calls = 0
        self.pwm = []

    def emergency_stop(self):
        self.stop_calls += 1
        return True

    def set_pwm(self, value):
        self.pwm.append(value)


def test_three_consecutive_missing_samples_trigger_emergency_stop():
    transport = StopTransport()
    controller = BreakinController(serial_controller=transport,
                                   measurement_manager=EmptyMeasurementManager())
    controller.running = True
    phase = BreakinPhase("TEST", duration_sec=10, pwm=60, direction="FWD", control="PWM")

    assert controller._collect_measurement(phase) is None
    assert controller._collect_measurement(phase) is None
    with pytest.raises(RuntimeError, match="3 consecutive invalid control samples"):
        controller._collect_measurement(phase)

    assert controller.running is False
    assert transport.stop_calls == 1


def test_three_consecutive_invalid_input_feedback_samples_trigger_stop():
    transport = StopTransport()
    controller = BreakinController(serial_controller=transport)
    controller.running = True
    controller.current_pwm = 100
    phase = BreakinPhase("TEST", duration_sec=10, pwm=100, direction="REV",
                         control="VOLTAGE", target_voltage=3.0,
                         pwm_min=0, pwm_max=255,
                         metadata={"voltage_control_mode": "INPUT"})
    invalid = {"voltage1": 3.0, "motor_voltage": -2.5}

    controller._voltage_control(phase, invalid)
    controller._voltage_control(phase, invalid)
    with pytest.raises(RuntimeError, match="3 consecutive invalid control samples"):
        controller._voltage_control(phase, invalid)

    assert controller.running is False
    assert transport.stop_calls == 1
