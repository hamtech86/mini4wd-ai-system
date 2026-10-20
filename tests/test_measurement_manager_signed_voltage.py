"""Validation tests for MOTOR_BREAKIN_V3 measurement frames."""

from measurement.measurement_manager import MeasurementManager


def valid_frame(**overrides):
    frame = {
        "record_type": "DATA",
        "device_model": "MOTOR_BREAKIN_V3",
        "instance_id": "000001",
        "elapsed_time": 1000,
        "raw_acs1": 512,
        "raw_acs2": 512,
        "current1": 0.2,
        "current2": 0.2,
        "voltage1": 0.5,
        "voltage2": 3.5,
        "motor_voltage": -3.0,
        "pwm": 80,
        "direction": "REV",
        "state": "RUNNING",
    }
    frame.update(overrides)
    return frame


def test_signed_negative_motor_voltage_is_valid_for_reverse():
    parsed = MeasurementManager()._parse_frame(valid_frame())
    assert parsed is not None
    assert parsed["motor_voltage"] == -3.0


def test_motor_voltage_outside_physical_difference_range_is_rejected():
    assert MeasurementManager()._parse_frame(
        valid_frame(motor_voltage=-12.1)
    ) is None
    assert MeasurementManager()._parse_frame(
        valid_frame(motor_voltage=12.1)
    ) is None


def test_missing_control_measurement_is_rejected_not_fabricated():
    frame = valid_frame()
    frame.pop("voltage2")
    assert MeasurementManager()._parse_frame(frame) is None


def test_non_data_frame_is_rejected():
    assert MeasurementManager()._parse_frame(
        valid_frame(record_type="INFO")
    ) is None
