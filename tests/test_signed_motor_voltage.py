"""Regression tests for the signed motor-terminal voltage contract."""
from measurement.measurement_manager import MeasurementManager


def data_frame(motor_voltage):
    return {
        "record_type": "DATA",
        "device_model": "MOTOR_BREAKIN_V3",
        "instance_id": "UNKNOWN",
        "elapsed_time": 1000,
        "raw_acs1": 500,
        "raw_acs2": 500,
        "current1": 0.1,
        "current2": 0.1,
        "voltage1": 3.0,
        "voltage2": 0.2,
        "motor_voltage": motor_voltage,
        "pwm": 60,
        "direction": "REV",
        "state": "RUN",
        "current_avg": 0.1,
        "power": 0.3,
        "current_ripple": 0.01,
        "voltage_ripple": 0.02,
        "peak_power": 0.4,
        "peak_current": 0.2,
        "peak_voltage": 3.1,
        "peak_pwm": 60,
        "brush_peak_current": 0.2,
        "raw_magnetic": 100,
        "magnetic_level": 0.1,
        "motor_temperature": 24.0,
    }


def test_reverse_signed_motor_voltage_is_valid():
    manager = MeasurementManager()
    parsed = manager._parse_frame(data_frame(-2.8))
    assert parsed is not None
    assert parsed["motor_voltage"] == -2.8


def test_motor_voltage_outside_signed_physical_range_is_rejected():
    manager = MeasurementManager()
    assert manager._parse_frame(data_frame(-12.1)) is None
    assert manager._parse_frame(data_frame(12.1)) is None



def test_incomplete_numeric_data_is_rejected():
    manager = MeasurementManager()
    frame = data_frame(-2.8)
    frame.pop("current_avg")
    assert manager._parse_frame(frame) is None


def test_fractional_adc_integer_field_is_rejected():
    manager = MeasurementManager()
    frame = data_frame(-2.8)
    frame["raw_acs1"] = 500.5
    assert manager._parse_frame(frame) is None
