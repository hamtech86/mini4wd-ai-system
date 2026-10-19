from measurement.measurement_manager import MeasurementManager


def valid_frame(**overrides):
    frame = {
        "record_type": "DATA", "elapsed_time": 100, "current1": 0.2,
        "current2": 0.1, "voltage1": 3.0, "voltage2": 4.0,
        "motor_voltage": -1.0, "pwm": 80, "direction": "REV", "state": "RUNNING",
    }
    frame.update(overrides)
    return frame


def test_parse_frame_accepts_signed_motor_voltage():
    parsed = MeasurementManager()._parse_frame(valid_frame())
    assert parsed is not None
    assert parsed["motor_voltage"] == -1.0


def test_parse_frame_rejects_motor_voltage_outside_absolute_bound():
    assert MeasurementManager()._parse_frame(valid_frame(motor_voltage=-12.1)) is None
    assert MeasurementManager()._parse_frame(valid_frame(motor_voltage=12.1)) is None


def test_parse_frame_rejects_missing_or_nonfinite_control_data():
    assert MeasurementManager()._parse_frame(valid_frame(voltage2=None)) is None
    assert MeasurementManager()._parse_frame(valid_frame(motor_voltage=float("nan"))) is None
