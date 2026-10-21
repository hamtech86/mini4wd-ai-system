"""Regression tests for the signed motor-terminal voltage contract."""
from measurement.measurement_manager import MeasurementManager


def data_frame(motor_voltage):
    return {
        "record_type": "DATA",
        "elapsed_time": 1000,
        "current1": 0.1,
        "current2": 0.1,
        "voltage1": 3.0,
        "voltage2": 0.2,
        "motor_voltage": motor_voltage,
        "pwm": 60,
        "direction": "REV",
        "state": "RUN",
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
