"""Strict validation for the independent RawLog v2 named-field schema.

This module validates persisted v2 records only. It does not parse Arduino
wire records, calibrate sensors, calculate engineering values, or mutate input.
"""
from __future__ import annotations

from datetime import datetime
import math
from typing import Mapping


SCHEMA_ID = "mini4wd.rawlog.v2"
RECORD_TYPES = {
    "SESSION", "MEASUREMENT", "ADC_SAMPLE", "CALIBRATION", "EVENT", "DERIVED"
}
CHANNELS = {"A0", "A1", "A4", "A5"}
DIRECTIONS = {"FWD", "REV", "STOP"}
SESSION_STATUSES = {"STARTED", "COMPLETE", "STOPPED", "INTERRUPTED", "FAULTED"}

MEASUREMENT_STRING_FIELDS = ("device_model", "instance_id", "state")
MEASUREMENT_INTEGER_FIELDS = (
    "raw_acs1", "raw_acs2", "pwm", "peak_pwm", "raw_magnetic"
)
MEASUREMENT_NUMBER_FIELDS = (
    "current1_a", "current2_a", "voltage1_v", "voltage2_v",
    "motor_voltage_v", "current_avg_a", "power_w", "current_ripple_a",
    "voltage_ripple_v", "peak_power_w", "peak_current_a",
    "peak_voltage_v", "brush_peak_current_a", "magnetic_level",
    "motor_temperature_c",
)
MEASUREMENT_FIELDS = (
    set(MEASUREMENT_STRING_FIELDS)
    | set(MEASUREMENT_INTEGER_FIELDS)
    | set(MEASUREMENT_NUMBER_FIELDS)
    | {"direction"}
)
COMMON_FIELDS = {
    "schema", "record_type", "log_id", "measurement_session_id",
    "record_id", "sequence", "elapsed_time_ms", "recorded_at",
}


class RawLogV2ValidationError(ValueError):
    """Raised when a RawLog v2 record violates the persisted schema."""


def _fail(message: str) -> None:
    raise RawLogV2ValidationError(message)


def _non_empty_string(value, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        _fail(f"{field} must be a non-empty string")


def _integer(value, field: str, minimum: int = 0, maximum: int | None = None) -> None:
    if type(value) is not int or value < minimum:
        _fail(f"{field} must be an integer >= {minimum}")
    if maximum is not None and value > maximum:
        _fail(f"{field} must be <= {maximum}")


def _finite_number(value, field: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"{field} must be a finite number")
    if not math.isfinite(float(value)):
        _fail(f"{field} must be a finite number")


def _nullable_number(value, field: str) -> None:
    if value is not None:
        _finite_number(value, field)


def _timestamp(value, field: str) -> None:
    _non_empty_string(value, field)
    candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        _fail(f"{field} must be an ISO-8601 timestamp")
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        _fail(f"{field} must include a timezone offset")


def _require(record: Mapping, fields: set[str], record_type: str) -> None:
    missing = sorted(fields - set(record))
    if missing:
        _fail(f"{record_type} missing required fields: {', '.join(missing)}")


def _validate_unavailable_fields(record: Mapping) -> set[str]:
    unavailable = record.get("unavailable_fields")
    if not isinstance(unavailable, list):
        _fail("MEASUREMENT unavailable_fields must be a list")
    result = set()
    for item in unavailable:
        if not isinstance(item, Mapping):
            _fail("each unavailable_fields item must be an object")
        _require(item, {"field", "reason"}, "unavailable_fields item")
        _non_empty_string(item["field"], "unavailable_fields.field")
        _non_empty_string(item["reason"], "unavailable_fields.reason")
        if item["field"] in result:
            _fail(f"duplicate unavailable field: {item['field']}")
        result.add(item["field"])
    return result


def _validate_measurement(record: Mapping) -> None:
    required = MEASUREMENT_FIELDS | {"unavailable_fields"}
    _require(record, required, "MEASUREMENT")

    for field in MEASUREMENT_STRING_FIELDS:
        _non_empty_string(record[field], field)

    if record["direction"] not in DIRECTIONS:
        _fail("direction must be FWD, REV, or STOP")

    for field in ("pwm",):
        _integer(record[field], field, 0, 255)

    for field in ("raw_acs1", "raw_acs2", "raw_magnetic"):
        value = record[field]
        if value is not None:
            _integer(value, field, 0, 1023)

    if record["peak_pwm"] is not None:
        _integer(record["peak_pwm"], "peak_pwm", 0, 255)

    for field in MEASUREMENT_NUMBER_FIELDS:
        _nullable_number(record[field], field)

    unavailable = _validate_unavailable_fields(record)
    for field in MEASUREMENT_FIELDS:
        if record[field] is None and field not in unavailable:
            _fail(f"{field} is null but has no unavailable_fields reason")
        if record[field] is not None and field in unavailable:
            _fail(f"{field} is marked unavailable but contains a value")


def _validate_adc_sample(record: Mapping) -> None:
    required = {
        "channel", "adc_raw", "timestamp_us", "acquisition_sequence",
        "phase", "direction", "pwm", "run_state",
    }
    _require(record, required, "ADC_SAMPLE")
    if record["channel"] not in CHANNELS:
        _fail("channel must be A0, A1, A4, or A5")
    _integer(record["adc_raw"], "adc_raw", 0, 1023)
    _integer(record["timestamp_us"], "timestamp_us", 0, (1 << 32) - 1)
    _integer(record["acquisition_sequence"], "acquisition_sequence", 0, (1 << 32) - 1)
    _non_empty_string(record["phase"], "phase")
    if record["direction"] not in DIRECTIONS:
        _fail("direction must be FWD, REV, or STOP")
    _integer(record["pwm"], "pwm", 0, 255)
    _non_empty_string(record["run_state"], "run_state")


def _validate_calibration(record: Mapping) -> None:
    required = {
        "sensor", "calibration_id", "calibration_version", "unit",
        "status", "offset", "scale", "source",
    }
    _require(record, required, "CALIBRATION")
    for field in ("sensor", "calibration_id", "calibration_version", "unit", "status", "source"):
        _non_empty_string(record[field], field)
    _nullable_number(record["offset"], "offset")
    _nullable_number(record["scale"], "scale")


def _validate_event(record: Mapping) -> None:
    _require(record, {"event_type", "details"}, "EVENT")
    _non_empty_string(record["event_type"], "event_type")
    if not isinstance(record["details"], Mapping):
        _fail("EVENT details must be an object")
    if record["event_type"] == "ROTATION_OBSERVATION":
        _require(record["details"], {"label"}, "ROTATION_OBSERVATION details")
        if record["details"]["label"] not in {"NO_ROTATION", "ROTATION", "UNKNOWN"}:
            _fail("rotation label must be NO_ROTATION, ROTATION, or UNKNOWN")


def _validate_derived(record: Mapping) -> None:
    required = {
        "metric", "algorithm_id", "algorithm_version", "input_record_ids",
        "value", "unit", "valid", "invalid_reason",
    }
    _require(record, required, "DERIVED")
    for field in ("metric", "algorithm_id", "algorithm_version", "unit"):
        _non_empty_string(record[field], field)
    if not isinstance(record["input_record_ids"], list) or any(
        not isinstance(item, str) or not item.strip()
        for item in record["input_record_ids"]
    ):
        _fail("input_record_ids must be a list of non-empty strings")
    if type(record["valid"]) is not bool:
        _fail("valid must be boolean")
    _nullable_number(record["value"], "value")
    if record["valid"]:
        if record["value"] is None or record["invalid_reason"] is not None:
            _fail("valid DERIVED record requires a finite value and null invalid_reason")
    else:
        _non_empty_string(record["invalid_reason"], "invalid_reason")


def validate_record(record: Mapping) -> None:
    """Validate one RawLog v2 JSON object without modifying it."""
    if not isinstance(record, Mapping):
        _fail("record must be an object")
    _require(record, COMMON_FIELDS, "record")
    if record["schema"] != SCHEMA_ID:
        _fail(f"schema must be {SCHEMA_ID}")
    record_type = record["record_type"]
    if record_type not in RECORD_TYPES:
        _fail(f"unsupported record_type: {record_type!r}")
    for field in ("log_id", "measurement_session_id", "record_id"):
        _non_empty_string(record[field], field)
    _integer(record["sequence"], "sequence")
    _integer(record["elapsed_time_ms"], "elapsed_time_ms")
    _timestamp(record["recorded_at"], "recorded_at")

    if record_type == "SESSION":
        _require(record, {"session_status", "device", "firmware", "measurement_plan"}, "SESSION")
        if record["session_status"] not in SESSION_STATUSES:
            _fail("invalid session_status")
        for field in ("device", "firmware", "measurement_plan"):
            if not isinstance(record[field], Mapping):
                _fail(f"{field} must be an object")
    elif record_type == "MEASUREMENT":
        _validate_measurement(record)
    elif record_type == "ADC_SAMPLE":
        _validate_adc_sample(record)
    elif record_type == "CALIBRATION":
        _validate_calibration(record)
    elif record_type == "EVENT":
        _validate_event(record)
    elif record_type == "DERIVED":
        _validate_derived(record)
