"""Regression tests for invalid-sample safety and physical current checks."""
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
        return {"serial_stop_attempted": True, "errors": []}

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


def test_physical_current1_spike_cannot_be_masked_by_current_avg():
    controller = BreakinController(serial_controller=StopTransport())
    controller.safety_config = {"max_current": 5.0, "max_motor_temperature": 70.0, "max_pwm": 255}
    measurement = {"current1": 5.2, "current2": 0.2, "current_avg": 0.1, "motor_temperature": 25.0}

    assert controller._current_from_measurement(measurement) == 5.2
    assert controller._safety_violation(measurement).startswith("SAFETY: current 5.20A")



@pytest.mark.parametrize("field,value", [
    ("raw_acs1", 0),
    ("raw_acs1", 2),
    ("raw_acs2", 1021),
    ("raw_acs2", 1023),
])
def test_acs712_adc_rail_fault_triggers_immediate_emergency_stop(field, value):
    transport = StopTransport()
    controller = BreakinController(serial_controller=transport)
    controller.running = True
    controller.current_pwm = 100
    phase = BreakinPhase("TEST", duration_sec=10, pwm=100, direction="FWD", control="PWM")
    measurement = {
        "record_type": "DATA",
        "raw_acs1": 512,
        "raw_acs2": 512,
        "current1": 0.2,
        "current2": 0.2,
        "current_avg": 0.2,
        "motor_temperature": 25.0,
    }
    measurement[field] = value

    class Manager:
        last_measurement = measurement
        def collect(self):
            return dict(measurement)

    controller.measurement_manager = Manager()
    with pytest.raises(RuntimeError, match="ACS712 sensor fault"):
        controller._collect_measurement(phase)

    assert controller.running is False
    assert transport.stop_calls == 1


def test_acs712_normal_adc_values_are_not_classified_as_rail_fault():
    measurement = {"raw_acs1": 512, "raw_acs2": 510}
    assert BreakinController._acs_adc_rail_fault(measurement) is None


@pytest.mark.parametrize("raw", [-1, 1024, float("nan"), 512.5, "bad"])
def test_acs712_invalid_adc_sample_is_classified_as_sensor_fault(raw):
    measurement = {"raw_acs1": raw, "raw_acs2": 512}
    assert BreakinController._acs_adc_rail_fault(measurement) is not None
