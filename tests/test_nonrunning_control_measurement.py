"""Regression tests for excluding idle/non-running telemetry from control input."""
from measurement.measurement_manager import MeasurementManager


def data_frame(state):
    return {
        "record_type": "DATA", "device_model": "MOTOR_BREAKIN_V3", "instance_id": 1,
        "elapsed_time": 0, "raw_acs1": 513, "raw_acs2": 515,
        "current1": 0.0, "current2": 0.0, "voltage1": 0.0, "voltage2": 0.0,
        "motor_voltage": 0.0, "pwm": 0, "direction": "FWD", "state": state,
        "current_avg": 0.0, "power": 0.0, "current_ripple": 0.0,
        "voltage_ripple": 0.0, "peak_power": 0.0, "peak_current": 0.0,
        "peak_voltage": 0.0, "peak_pwm": 0, "brush_peak_current": 0.0,
        "raw_magnetic": 538, "magnetic_level": 2.63, "motor_temperature": 26.7,
    }


def test_ready_frame_is_not_a_control_measurement():
    manager = MeasurementManager()
    assert manager._parse_frame(data_frame("READY")) is None


def test_pause_stop_complete_and_error_frames_are_not_control_measurements():
    manager = MeasurementManager()
    for state in ("PAUSE", "STOP", "COMPLETE", "ERROR", "UNKNOWN"):
        assert manager._parse_frame(data_frame(state)) is None


def test_running_frame_remains_a_valid_control_measurement():
    manager = MeasurementManager()
    parsed = manager._parse_frame(data_frame("RUN"))
    assert parsed is not None
    assert parsed["state"] == "RUN"
