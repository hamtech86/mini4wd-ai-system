from copy import deepcopy

import pytest

from raw_log_library.v2_schema import (
    RawLogV2ValidationError,
    SCHEMA_ID,
    validate_record,
)


def _base(record_type):
    return {
        "schema": SCHEMA_ID,
        "record_type": record_type,
        "log_id": "MOTOR-000123",
        "measurement_session_id": "session-001",
        "record_id": "record-0001",
        "sequence": 0,
        "elapsed_time_ms": 0,
        "recorded_at": "2026-10-31T10:00:00+09:00",
    }


def _measurement():
    record = _base("MEASUREMENT")
    record.update({
        "device_model": "MOTOR_BREAKIN_V3",
        "instance_id": "000001",
        "raw_acs1": 512,
        "raw_acs2": 510,
        "current1_a": 0.01,
        "current2_a": 0.02,
        "voltage1_v": 3.0,
        "voltage2_v": 0.1,
        "motor_voltage_v": 2.9,
        "pwm": 4,
        "direction": "FWD",
        "state": "MEASURE",
        "current_avg_a": 0.01,
        "power_w": 0.029,
        "current_ripple_a": 0.001,
        "voltage_ripple_v": 0.002,
        "peak_power_w": 0.03,
        "peak_current_a": 0.011,
        "peak_voltage_v": 3.0,
        "peak_pwm": 4,
        "brush_peak_current_a": 0.02,
        "raw_magnetic": 500,
        "magnetic_level": 0.5,
        "motor_temperature_c": 25.0,
        "unavailable_fields": [],
    })
    return record


def test_accepts_full_measurement_item_set():
    record = _measurement()
    validate_record(record)
    assert len(record) >= 30


def test_measurement_requires_all_former_measurement_items():
    record = _measurement()
    del record["brush_peak_current_a"]
    with pytest.raises(RawLogV2ValidationError, match="brush_peak_current_a"):
        validate_record(record)


def test_null_measurement_value_requires_explicit_unavailable_reason():
    record = _measurement()
    record["motor_temperature_c"] = None
    with pytest.raises(RawLogV2ValidationError, match="no unavailable_fields reason"):
        validate_record(record)


def test_null_measurement_value_is_allowed_with_reason():
    record = _measurement()
    record["motor_temperature_c"] = None
    record["unavailable_fields"] = [{
        "field": "motor_temperature_c",
        "reason": "sensor_not_fitted",
    }]
    validate_record(record)


def test_rejects_nan_in_measurement():
    record = _measurement()
    record["current1_a"] = float("nan")
    with pytest.raises(RawLogV2ValidationError, match="finite"):
        validate_record(record)


def test_accepts_individual_adc_sample_timestamp():
    record = _base("ADC_SAMPLE")
    record.update({
        "channel": "A0",
        "adc_raw": 514,
        "timestamp_us": 123456,
        "acquisition_sequence": 7,
        "phase": "WINDING",
        "direction": "FWD",
        "pwm": 4,
        "run_state": "MEASURE",
    })
    validate_record(record)


def test_rejects_adc_timestamp_out_of_uint32_range():
    record = _base("ADC_SAMPLE")
    record.update({
        "channel": "A4",
        "adc_raw": 500,
        "timestamp_us": 1 << 32,
        "acquisition_sequence": 7,
        "phase": "WINDING",
        "direction": "FWD",
        "pwm": 4,
        "run_state": "MEASURE",
    })
    with pytest.raises(RawLogV2ValidationError, match="timestamp_us"):
        validate_record(record)


def test_rotation_observation_accepts_all_three_labels():
    for label in ("NO_ROTATION", "ROTATION", "UNKNOWN"):
        record = _base("EVENT")
        record.update({
            "event_type": "ROTATION_OBSERVATION",
            "details": {"label": label, "pwm": 4},
        })
        validate_record(record)


def test_rotation_observation_rejects_unknown_label():
    record = _base("EVENT")
    record.update({
        "event_type": "ROTATION_OBSERVATION",
        "details": {"label": "MAYBE"},
    })
    with pytest.raises(RawLogV2ValidationError, match="rotation label"):
        validate_record(record)


def test_valid_derived_result_requires_value_and_no_invalid_reason():
    record = _base("DERIVED")
    record.update({
        "metric": "winding_current_candidate",
        "algorithm_id": "a0_detectability_v1",
        "algorithm_version": "0.1.0",
        "input_record_ids": ["record-0001"],
        "value": 0.012,
        "unit": "A",
        "valid": True,
        "invalid_reason": None,
    })
    validate_record(record)


def test_invalid_derived_result_requires_reason():
    record = _base("DERIVED")
    record.update({
        "metric": "winding_current_candidate",
        "algorithm_id": "a0_detectability_v1",
        "algorithm_version": "0.1.0",
        "input_record_ids": ["record-0001"],
        "value": None,
        "unit": "A",
        "valid": False,
        "invalid_reason": "rotation_observed",
    })
    validate_record(record)


def test_rejects_naive_timestamp_without_timezone():
    record = _measurement()
    record["recorded_at"] = "2026-10-31T10:00:00"
    with pytest.raises(RawLogV2ValidationError, match="timezone"):
        validate_record(record)
