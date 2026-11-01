"""Strict RawLog v2 schema and cross-record validation."""
from __future__ import annotations

import json
import math
import re
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

SCHEMA_NAME = "mini4wd.rawlog"
SCHEMA_VERSION = "2.0.0"
MEASUREMENT_TYPE = "PWM_START_SWEEP_310S"
RECORD_TYPES = {"SESSION_EVENT", "PWM_STAGE", "ADC_SAMPLE", "CALIBRATION", "EVENT", "DERIVED"}
CHANNELS = {
    "A0": ("ACS712 #1", "winding_current"),
    "A1": ("ACS712 #2", "brush_stability_observation"),
    "A2": ("magnetic_sensor", "magnetic_reference"),
    "A3": ("thermistor", "thermistor_reference"),
    "A4": ("voltage_input_v4", "voltage_v4"),
    "A5": ("voltage_input_v5", "voltage_v5"),
}
UTC_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z$")
CAL_CHANNELS = {
    "A0": ("winding_current", "winding_current_zero_reference"),
    "A1": ("brush_stability_observation", "brush_observation_reference"),
    "A4": ("voltage_v4", "voltage_input_reference"),
    "A5": ("voltage_v5", "voltage_input_reference"),
}


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _utc(value: Any) -> bool:
    if not isinstance(value, str) or not UTC_RE.fullmatch(value):
        return False
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
        return True
    except ValueError:
        return False


def parse_complete_jsonl(raw: bytes) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Parse a strict UTF-8 JSONL byte stream; every row must end in LF."""
    records: List[Dict[str, Any]] = []
    errors: List[str] = []
    if not raw:
        return records, errors
    if not raw.endswith(b"\n"):
        errors.append("records.jsonl has an unterminated final line")
    lines = raw.splitlines(keepends=True)
    for index, line in enumerate(lines, 1):
        if not line.endswith(b"\n"):
            continue
        if line in (b"\n", b"\r\n"):
            errors.append(f"line {index}: blank JSONL line")
            continue
        try:
            value = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            errors.append(f"line {index}: invalid JSON: {exc}")
            continue
        if not isinstance(value, dict):
            errors.append(f"line {index}: JSON value must be an object")
            continue
        records.append(value)
    return records, errors


def validate_manifest(manifest: Any) -> List[str]:
    errors: List[str] = []
    if not isinstance(manifest, dict):
        return ["manifest must be a JSON object"]
    required = {
        "schema_name", "schema_version", "log_id", "measurement_session_id",
        "measurement_type", "created_at_utc", "started_at_utc", "ended_at_utc",
        "status", "planned_stage_count", "planned_stage_duration_ms",
        "planned_total_duration_ms", "motor_instance_id", "device",
        "measurement_conditions", "record_counts",
    }
    for key in sorted(required - set(manifest)):
        errors.append(f"manifest missing required field: {key}")
    if manifest.get("schema_name") != SCHEMA_NAME:
        errors.append("manifest.schema_name must be mini4wd.rawlog")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append("manifest.schema_version must be 2.0.0")
    if manifest.get("measurement_type") != MEASUREMENT_TYPE:
        errors.append("manifest.measurement_type is invalid")
    for key in ("log_id", "measurement_session_id"):
        if key in manifest and (not isinstance(manifest[key], str) or not manifest[key]):
            errors.append(f"manifest.{key} must be a non-empty string")
    for key in ("created_at_utc", "started_at_utc"):
        if key in manifest and not _utc(manifest[key]):
            errors.append(f"manifest.{key} must be an ISO-8601 UTC timestamp ending in Z")
    ended = manifest.get("ended_at_utc")
    if ended is not None and not _utc(ended):
        errors.append("manifest.ended_at_utc must be null or an ISO-8601 UTC timestamp ending in Z")
    if _utc(manifest.get("started_at_utc")) and _utc(ended) and ended < manifest["started_at_utc"]:
        errors.append("manifest.ended_at_utc precedes started_at_utc")
    if _utc(manifest.get("created_at_utc")) and _utc(ended) and manifest["created_at_utc"] < ended:
        errors.append("manifest.created_at_utc precedes ended_at_utc")
    if isinstance(manifest.get("status"), str) and manifest.get("status") in {"completed", "aborted"} and ended is None:
        errors.append("completed/aborted manifest requires ended_at_utc")
    if not isinstance(manifest.get("status"), str) or manifest.get("status") not in {"completed", "aborted", "incomplete"}:
        errors.append("manifest.status is invalid")
    for key, expected in (("planned_stage_count", 31), ("planned_stage_duration_ms", 10000),
                          ("planned_total_duration_ms", 310000)):
        if manifest.get(key) != expected or not _is_int(manifest.get(key)):
            errors.append(f"manifest.{key} must be {expected}")
    if manifest.get("motor_instance_id") is not None and not isinstance(manifest.get("motor_instance_id"), str):
        errors.append("manifest.motor_instance_id must be string or null")

    device = manifest.get("device")
    if not isinstance(device, dict):
        errors.append("manifest.device must be an object")
    else:
        for key in ("type", "model", "firmware_version", "firmware_build", "firmware_id", "adc_resolution_bits"):
            if key not in device:
                errors.append(f"manifest.device missing {key}")
        for key in ("type", "model", "firmware_version", "firmware_build", "firmware_id"):
            if key in device and device[key] is not None and not isinstance(device[key], str):
                errors.append(f"manifest.device.{key} must be string or null")
        bits = device.get("adc_resolution_bits")
        if bits is not None and (not _is_int(bits) or not 1 <= bits <= 32):
            errors.append("manifest.device.adc_resolution_bits must be null or integer 1..32")

    conditions = manifest.get("measurement_conditions")
    if not isinstance(conditions, dict):
        errors.append("manifest.measurement_conditions must be an object")
    else:
        if not isinstance(conditions.get("direction"), str) or conditions.get("direction") not in {"FWD", "REV", "UNKNOWN"}:
            errors.append("measurement_conditions.direction is invalid")
        if not isinstance(conditions.get("voltage_control_mode"), str) or conditions.get("voltage_control_mode") not in {"INPUT", "TERMINAL", "NOT_APPLICABLE", "UNKNOWN"}:
            errors.append("measurement_conditions.voltage_control_mode is invalid")
        fixed = {"sweep_pwm_min": 0, "sweep_pwm_max": 30, "stage_duration_ms": 10000, "schedule_owner": "PYTHON"}
        for key, expected in fixed.items():
            value = conditions.get(key)
            if value != expected or (key != "schedule_owner" and not _is_int(value)):
                errors.append(f"measurement_conditions.{key} must be {expected}")
    warnings = manifest.get("metadata_warnings", [])
    if not isinstance(warnings, list) or any(not isinstance(item, str) for item in warnings):
        errors.append("manifest.metadata_warnings must be an array of strings")
    counts = manifest.get("record_counts")
    if not isinstance(counts, dict) or any(not isinstance(k, str) or not _is_int(v) or v < 0 for k, v in counts.items()):
        errors.append("manifest.record_counts must map record type strings to non-negative integers")
    return errors


def _require(record: Dict[str, Any], fields: Iterable[str], prefix: str, errors: List[str]) -> None:
    for field in fields:
        if field not in record:
            errors.append(f"{prefix} missing required field: {field}")


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def validate_record(record: Any, manifest: Dict[str, Any], index: int = 0) -> List[str]:
    prefix = f"record[{index}]"
    errors: List[str] = []
    if not isinstance(record, dict):
        return [f"{prefix} must be an object"]
    common = ("schema_version", "record_type", "record_id", "record_seq", "log_id",
              "measurement_session_id", "recorded_at_utc")
    _require(record, common, prefix, errors)
    if record.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"{prefix}.schema_version must be 2.0.0")
    kind = record.get("record_type")
    if not isinstance(kind, str) or kind not in RECORD_TYPES:
        errors.append(f"{prefix}.record_type is unknown")
        return errors
    for key in ("record_id", "log_id", "measurement_session_id"):
        if key in record and not _nonempty_string(record[key]):
            errors.append(f"{prefix}.{key} must be a non-empty string")
    if "record_seq" in record and (not _is_int(record["record_seq"]) or record["record_seq"] < 1):
        errors.append(f"{prefix}.record_seq must be a positive integer")
    if "recorded_at_utc" in record and not _utc(record["recorded_at_utc"]):
        errors.append(f"{prefix}.recorded_at_utc must be UTC ISO-8601 ending in Z")
    if record.get("log_id") != manifest.get("log_id"):
        errors.append(f"{prefix}.log_id differs from manifest")
    if record.get("measurement_session_id") != manifest.get("measurement_session_id"):
        errors.append(f"{prefix}.measurement_session_id differs from manifest")

    if kind == "SESSION_EVENT":
        _require(record, ("event", "host_monotonic_ns", "details"), prefix, errors)
        if not isinstance(record.get("event"), str) or record.get("event") not in {"SESSION_STARTED", "SESSION_COMPLETED", "SESSION_ABORTED",
            "COMMUNICATION_LOST", "STOP_REQUESTED", "DEVICE_STATE_REPORTED", "OTHER"}:
            errors.append(f"{prefix}.event is invalid")
        if not _is_int(record.get("host_monotonic_ns")) or record.get("host_monotonic_ns", -1) < 0:
            errors.append(f"{prefix}.host_monotonic_ns must be a non-negative integer")
        if not isinstance(record.get("details"), dict):
            errors.append(f"{prefix}.details must be an object")

    elif kind == "PWM_STAGE":
        fields = ("stage_id", "stage_index", "pwm_command", "planned_duration_ms", "stage_status",
            "started_at_utc", "ended_at_utc", "start_host_monotonic_ns", "end_host_monotonic_ns",
            "actual_duration_ms", "pwm_command_sent_at_utc", "pwm_applied_ack_received_at_utc",
            "output_state", "stage_context_id", "termination_reason")
        _require(record, fields, prefix, errors)
        idx = record.get("stage_index")
        if not _is_int(idx) or not 0 <= idx <= 30:
            errors.append(f"{prefix}.stage_index must be integer 0..30")
        else:
            if record.get("stage_id") != f"PWM-{idx:02d}" or not _is_int(record.get("pwm_command")) or record.get("pwm_command") != idx:
                errors.append(f"{prefix} stage_id/pwm_command must match stage_index")
        if not _is_int(record.get("planned_duration_ms")) or record.get("planned_duration_ms") != 10000:
            errors.append(f"{prefix}.planned_duration_ms must be 10000")
        if not isinstance(record.get("stage_status"), str) or record.get("stage_status") not in {"completed", "aborted", "not_reached"}:
            errors.append(f"{prefix}.stage_status is invalid")
        if not isinstance(record.get("output_state"), str) or record.get("output_state") not in {"reported_on", "reported_off", "unknown"}:
            errors.append(f"{prefix}.output_state is invalid")
        if not isinstance(record.get("termination_reason"), str) or record.get("termination_reason") not in {"duration_elapsed", "user_stop", "safety_stop",
            "communication_lost", "process_interrupted", "not_started_after_abort", "other"}:
            errors.append(f"{prefix}.termination_reason is invalid")
        for key in ("started_at_utc", "ended_at_utc", "pwm_command_sent_at_utc", "pwm_applied_ack_received_at_utc"):
            if record.get(key) is not None and not _utc(record[key]):
                errors.append(f"{prefix}.{key} must be null or UTC ISO-8601")
        for key in ("start_host_monotonic_ns", "end_host_monotonic_ns"):
            val = record.get(key)
            if val is not None and (not _is_int(val) or val < 0):
                errors.append(f"{prefix}.{key} must be null or non-negative integer")
        duration = record.get("actual_duration_ms")
        if duration is not None and (not _is_number(duration) or duration < 0):
            errors.append(f"{prefix}.actual_duration_ms must be null or non-negative number")
        if record.get("stage_context_id") is not None and not _nonempty_string(record["stage_context_id"]):
            errors.append(f"{prefix}.stage_context_id must be non-empty string or null")
        if record.get("stage_status") == "not_reached":
            for key in ("started_at_utc", "ended_at_utc", "start_host_monotonic_ns",
                        "end_host_monotonic_ns", "actual_duration_ms", "pwm_command_sent_at_utc",
                        "pwm_applied_ack_received_at_utc", "stage_context_id"):
                if record.get(key) is not None:
                    errors.append(f"{prefix}.{key} must be null for not_reached")
            if record.get("termination_reason") != "not_started_after_abort":
                errors.append(f"{prefix}.not_reached requires not_started_after_abort")
        if record.get("stage_status") == "completed" and record.get("termination_reason") != "duration_elapsed":
            errors.append(f"{prefix}.completed requires duration_elapsed")
        status = record.get("stage_status")
        if status == "completed":
            if any(record.get(k) is None for k in ("started_at_utc", "ended_at_utc",
                    "start_host_monotonic_ns", "end_host_monotonic_ns", "actual_duration_ms",
                    "pwm_command_sent_at_utc", "pwm_applied_ack_received_at_utc", "stage_context_id")):
                errors.append(f"{prefix}.completed requires ACK, context, start/end and duration fields")
        elif status == "aborted":
            if record.get("ended_at_utc") is None or record.get("pwm_command_sent_at_utc") is None:
                errors.append(f"{prefix}.aborted requires an end boundary and command-send timestamp")
            if record.get("started_at_utc") is None:
                if any(record.get(k) is not None for k in ("start_host_monotonic_ns", "actual_duration_ms",
                        "pwm_applied_ack_received_at_utc")):
                    errors.append(f"{prefix}.aborted without ACK cannot claim start/duration")
            elif any(record.get(k) is None for k in ("start_host_monotonic_ns", "end_host_monotonic_ns", "actual_duration_ms",
                    "pwm_applied_ack_received_at_utc", "stage_context_id")):
                errors.append(f"{prefix}.aborted after ACK requires context and measured timing")
        if _utc(record.get("started_at_utc")) and _utc(record.get("ended_at_utc")):
            if record["ended_at_utc"] < record["started_at_utc"]:
                errors.append(f"{prefix} stage end precedes start")
        if record.get("started_at_utc") is not None and record.get("pwm_applied_ack_received_at_utc") != record.get("started_at_utc"):
            errors.append(f"{prefix}.started_at_utc must equal ACK receive time")
        if _is_int(record.get("start_host_monotonic_ns")) and _is_int(record.get("end_host_monotonic_ns")):
            if record["end_host_monotonic_ns"] < record["start_host_monotonic_ns"]:
                errors.append(f"{prefix} monotonic end precedes start")
            else:
                expected_ms = (record["end_host_monotonic_ns"] - record["start_host_monotonic_ns"]) / 1_000_000
                if _is_number(record.get("actual_duration_ms")) and abs(record["actual_duration_ms"] - expected_ms) > 0.001:
                    errors.append(f"{prefix}.actual_duration_ms does not match monotonic interval")
        if _utc(record.get("ended_at_utc")) and _utc(record.get("recorded_at_utc")) and record["recorded_at_utc"] < record["ended_at_utc"]:
            errors.append(f"{prefix}.recorded_at_utc precedes stage end")

    elif kind == "ADC_SAMPLE":
        fields = ("sample_id", "channel", "sensor", "signal_role", "adc_raw", "adc_resolution_bits",
            "raw_unit", "device_timestamp_us_u32", "device_timestamp_point", "device_epoch_id",
            "device_elapsed_us", "device_sample_sequence", "host_received_at_utc",
            "host_received_monotonic_ns", "stage_context_id", "stage_id", "stage_assignment",
            "calibration_id", "validity", "invalid_reason")
        _require(record, fields, prefix, errors)
        channel = record.get("channel")
        if not isinstance(channel, str) or channel not in CHANNELS:
            errors.append(f"{prefix}.channel is invalid")
        else:
            sensor, role = CHANNELS[channel]
            if record.get("sensor") != sensor or record.get("signal_role") != role:
                errors.append(f"{prefix} sensor/signal_role does not match {channel}")
        if not _nonempty_string(record.get("sample_id")):
            errors.append(f"{prefix}.sample_id must be non-empty")
        raw = record.get("adc_raw")
        if raw is not None and (not _is_int(raw) or raw < 0):
            errors.append(f"{prefix}.adc_raw must be non-negative integer or null")
        bits = record.get("adc_resolution_bits")
        if not _is_int(bits) or not 1 <= bits <= 32:
            errors.append(f"{prefix}.adc_resolution_bits must be integer 1..32")
        elif _is_int(raw) and raw >= (1 << bits):
            errors.append(f"{prefix}.adc_raw exceeds ADC resolution")
        if record.get("raw_unit") != "count":
            errors.append(f"{prefix}.raw_unit must be count")
        stamp = record.get("device_timestamp_us_u32")
        if stamp is not None and (not _is_int(stamp) or not 0 <= stamp <= 0xFFFFFFFF):
            errors.append(f"{prefix}.device_timestamp_us_u32 must be uint32 or null")
        for key in ("device_epoch_id",):
            if not _nonempty_string(record.get(key)):
                errors.append(f"{prefix}.{key} must be non-empty")
        for key in ("device_elapsed_us", "device_sample_sequence"):
            val = record.get(key)
            if val is not None and (not _is_int(val) or val < 0):
                errors.append(f"{prefix}.{key} must be null or non-negative integer")
        if not _is_int(record.get("host_received_monotonic_ns")) or record.get("host_received_monotonic_ns", -1) < 0:
            errors.append(f"{prefix}.host_received_monotonic_ns must be a non-negative integer")
        device_bits = manifest.get("device", {}).get("adc_resolution_bits") if isinstance(manifest.get("device"), dict) else None
        if _is_int(device_bits) and _is_int(bits) and bits != device_bits:
            errors.append(f"{prefix}.adc_resolution_bits differs from manifest.device")
        if not _utc(record.get("host_received_at_utc")):
            errors.append(f"{prefix}.host_received_at_utc must be UTC ISO-8601")
        if not _nonempty_string(record.get("device_timestamp_point")):
            errors.append(f"{prefix}.device_timestamp_point must be a non-empty string")
        if not isinstance(record.get("stage_assignment"), str) or record.get("stage_assignment") not in {"confirmed", "unresolved"}:
            errors.append(f"{prefix}.stage_assignment is invalid")
        if record.get("stage_id") is not None and not re.fullmatch(r"PWM-(?:0[0-9]|[12][0-9]|30)", str(record["stage_id"])):
            errors.append(f"{prefix}.stage_id is invalid")
        if record.get("stage_assignment") == "unresolved" and record.get("stage_id") is not None:
            errors.append(f"{prefix}.unresolved sample cannot claim stage_id")
        if record.get("stage_context_id") is not None and not _nonempty_string(record["stage_context_id"]):
            errors.append(f"{prefix}.stage_context_id must be non-empty string or null")
        if not isinstance(record.get("validity"), str) or record.get("validity") not in {"valid", "invalid", "unavailable"}:
            errors.append(f"{prefix}.validity is invalid")
        if record.get("validity") == "valid":
            if raw is None or stamp is None or record.get("invalid_reason") is not None:
                errors.append(f"{prefix}.valid sample requires raw/timestamp and null invalid_reason")
        if record.get("validity") == "unavailable":
            if raw is not None or stamp is not None or not _nonempty_string(record.get("invalid_reason")):
                errors.append(f"{prefix}.unavailable sample requires null raw/timestamp and reason")
        if record.get("validity") == "invalid" and not _nonempty_string(record.get("invalid_reason")):
            errors.append(f"{prefix}.invalid sample requires invalid_reason")
        if channel == "A1" and ("converted_value" in record or "converted_unit" in record):
            errors.append(f"{prefix}.A1 conversion is not permitted by the current schema")
        if isinstance(channel, str) and channel in {"A0", "A4", "A5"} and record.get("converted_value") is not None:
            if not _is_number(record.get("converted_value")):
                errors.append(f"{prefix}.converted_value must be numeric")
            if record.get("calibration_id") is None:
                errors.append(f"{prefix} converted value requires calibration_id")
            if not isinstance(record.get("converted_unit"), str) or not record.get("converted_unit"):
                errors.append(f"{prefix} converted value requires converted_unit")
        if channel == "A0" and record.get("converted_value") is not None and record.get("converted_unit") != "A":
            errors.append(f"{prefix}.A0 converted_unit must be A")
        if isinstance(channel, str) and channel in {"A4", "A5"} and record.get("converted_value") is not None and record.get("converted_unit") != "V":
            errors.append(f"{prefix}.{channel} converted_unit must be V")


    elif kind == "CALIBRATION":
        fields = ("calibration_id", "source", "raw_line", "captured_at_utc",
            "captured_host_monotonic_ns", "effective_from_event_id", "effective_until_event_id",
            "application_status", "channels")
        _require(record, fields, prefix, errors)
        if not _nonempty_string(record.get("calibration_id")):
            errors.append(f"{prefix}.calibration_id must be non-empty and unique")
        if not isinstance(record.get("source"), str) or record.get("source") not in {"firmware_CAL_line", "host_calibration", "manual_calibration"}:
            errors.append(f"{prefix}.source is invalid")
        if record.get("source") == "firmware_CAL_line" and not isinstance(record.get("raw_line"), str):
            errors.append(f"{prefix}.firmware_CAL_line requires raw_line string")
        if record.get("raw_line") is not None and not isinstance(record.get("raw_line"), str):
            errors.append(f"{prefix}.raw_line must be string or null")
        if not _utc(record.get("captured_at_utc")):
            errors.append(f"{prefix}.captured_at_utc must be UTC ISO-8601")
        val = record.get("captured_host_monotonic_ns")
        if not _is_int(val) or val < 0:
            errors.append(f"{prefix}.captured_host_monotonic_ns must be non-negative integer")
        for key in ("effective_from_event_id", "effective_until_event_id"):
            if record.get(key) is not None and not _nonempty_string(record[key]):
                errors.append(f"{prefix}.{key} must be non-empty string or null")
        status = record.get("application_status")
        if not isinstance(status, str) or status not in {"raw_capture_only", "scoped_for_application", "application_scope_unresolved"}:
            errors.append(f"{prefix}.application_status is invalid")
        channels = record.get("channels")
        if not isinstance(channels, dict) or set(channels) != set(CAL_CHANNELS):
            errors.append(f"{prefix}.channels must contain exactly A0/A1/A4/A5")
        else:
            for ch, (role, cal_role) in CAL_CHANNELS.items():
                item = channels[ch]
                if not isinstance(item, dict):
                    errors.append(f"{prefix}.channels.{ch} must be an object")
                    continue
                if item.get("signal_role") != role or item.get("calibration_role") != cal_role:
                    errors.append(f"{prefix}.channels.{ch} role mismatch")
                if item.get("parameter_status") != "raw_only_unparsed" or item.get("parameters") is not None:
                    errors.append(f"{prefix}.channels.{ch} must remain raw_only_unparsed with null parameters")
        if status == "scoped_for_application":
            errors.append(f"{prefix}.scoped_for_application is not permitted while the current schema channels are raw-only")

    elif kind == "EVENT":
        _require(record, ("event", "observation_method", "actor", "observed_at_utc",
            "reported_at_utc", "host_monotonic_ns", "stage_id", "stage_index", "pwm_value"), prefix, errors)
        if not isinstance(record.get("event"), str) or record.get("event") not in {"ROTATION_START_CONFIRMED", "ROTATION_NOT_OBSERVED_AT_STAGE"}:
            errors.append(f"{prefix}.event is invalid")
        if record.get("observation_method") != "human_visual":
            errors.append(f"{prefix}.observation_method must be human_visual")
        if not _nonempty_string(record.get("actor")):
            errors.append(f"{prefix}.actor must be non-empty")
        for key in ("observed_at_utc", "reported_at_utc"):
            if not _utc(record.get(key)):
                errors.append(f"{prefix}.{key} must be UTC ISO-8601")
        if not _is_int(record.get("host_monotonic_ns")) or record.get("host_monotonic_ns", -1) < 0:
            errors.append(f"{prefix}.host_monotonic_ns must be non-negative integer")
        if record.get("stage_id") is None or record.get("stage_index") is None or record.get("pwm_value") is None:
            if not all(record.get(k) is None for k in ("stage_id", "stage_index", "pwm_value")):
                errors.append(f"{prefix} stage_id/index/pwm_value must all be null or all supplied")
        elif not (_is_int(record["stage_index"]) and 0 <= record["stage_index"] <= 30
                  and record["stage_id"] == f"PWM-{record['stage_index']:02d}"
                  and record["pwm_value"] == record["stage_index"]):
            errors.append(f"{prefix} stage_id/index/pwm_value do not identify one matching PWM stage")

    elif kind == "DERIVED":
        _require(record, ("metric", "algorithm_id", "algorithm_version", "input_sample_ids",
            "value", "unit", "valid", "invalid_reason"), prefix, errors)
        if not _nonempty_string(record.get("metric")) or not _nonempty_string(record.get("algorithm_id")):
            errors.append(f"{prefix}.metric and algorithm_id must be non-empty strings")
        if not _nonempty_string(record.get("algorithm_version")) or not isinstance(record.get("unit"), str):
            errors.append(f"{prefix}.algorithm_version/unit must be strings")
        if not isinstance(record.get("input_sample_ids"), list) or any(not _nonempty_string(x) for x in record.get("input_sample_ids", [])):
            errors.append(f"{prefix}.input_sample_ids must be an array of sample IDs")
        if not isinstance(record.get("valid"), bool):
            errors.append(f"{prefix}.valid must be boolean")
        if record.get("valid") and (record.get("value") is None or record.get("invalid_reason") is not None):
            errors.append(f"{prefix}.valid DERIVED requires value and null invalid_reason")
        if not record.get("valid") and (record.get("value") is not None or not _nonempty_string(record.get("invalid_reason"))):
            errors.append(f"{prefix}.invalid DERIVED requires null value and reason")
    return errors


def validate_package(manifest: Any, records: Any, raise_on_error: bool = True) -> List[str]:
    errors = validate_manifest(manifest)
    if not isinstance(records, list):
        errors.append("records must be a list")
        records = []
    if not isinstance(manifest, dict):
        if raise_on_error:
            raise ValueError("; ".join(errors))
        return errors

    seen_ids = set()
    seen_samples = set()
    seen_calibrations = set()
    stages: Dict[int, Dict[str, Any]] = {}
    contexts: Dict[str, Dict[str, Any]] = {}
    actual_counts: Dict[str, int] = {}
    for index, record in enumerate(records):
        errors.extend(validate_record(record, manifest, index))
        if not isinstance(record, dict):
            continue
        rid = record.get("record_id")
        if isinstance(rid, str):
            if rid in seen_ids:
                errors.append(f"duplicate record_id: {rid}")
            seen_ids.add(rid)
        seq = record.get("record_seq")
        if seq != index + 1:
            errors.append(f"record_seq at row {index + 1} must be {index + 1}, got {seq}")
        kind = record.get("record_type")
        if isinstance(kind, str):
            actual_counts[kind] = actual_counts.get(kind, 0) + 1
        if kind == "ADC_SAMPLE":
            sid = record.get("sample_id")
            if isinstance(sid, str):
                if sid in seen_samples:
                    errors.append(f"duplicate sample_id: {sid}")
                seen_samples.add(sid)
        elif kind == "CALIBRATION":
            cid = record.get("calibration_id")
            if isinstance(cid, str):
                if cid in seen_calibrations:
                    errors.append(f"duplicate calibration_id: {cid}")
                seen_calibrations.add(cid)
        elif kind == "PWM_STAGE":
            idx = record.get("stage_index")
            if _is_int(idx):
                if idx in stages:
                    errors.append(f"duplicate PWM_STAGE stage_index: {idx}")
                stages[idx] = record
                context = record.get("stage_context_id")
                if isinstance(context, str):
                    if context in contexts:
                        errors.append(f"duplicate PWM_STAGE stage_context_id: {context}")
                    contexts[context] = record

    counts = manifest.get("record_counts")
    if isinstance(counts, dict) and counts != actual_counts:
        errors.append(f"manifest.record_counts mismatch: expected {actual_counts}, got {counts}")

    for record in records:
        if not isinstance(record, dict):
            continue
        if record.get("record_type") == "ADC_SAMPLE":
            context = record.get("stage_context_id")
            assignment = record.get("stage_assignment")
            stage = contexts.get(context) if isinstance(context, str) else None
            if assignment == "confirmed":
                if stage is None:
                    errors.append(f"ADC_SAMPLE {record.get('sample_id')} confirmed context has no PWM_STAGE")
                elif record.get("stage_id") != stage.get("stage_id"):
                    errors.append(f"ADC_SAMPLE {record.get('sample_id')} stage_id/context mismatch")
            if record.get("calibration_id") is not None:
                cal = next((r for r in records if isinstance(r, dict)
                            and r.get("record_type") == "CALIBRATION"
                            and r.get("calibration_id") == record.get("calibration_id")), None)
                if cal is None:
                    errors.append(f"ADC_SAMPLE {record.get('sample_id')} references unknown calibration_id")
                elif cal.get("application_status") != "scoped_for_application":
                    errors.append(f"ADC_SAMPLE {record.get('sample_id')} references non-applicable raw-only calibration")
                elif not isinstance(record.get("channel"), str) or record.get("channel") not in cal.get("channels", {}):
                    errors.append(f"ADC_SAMPLE {record.get('sample_id')} calibration has no matching channel")
        if record.get("record_type") == "EVENT" and record.get("stage_id") is not None:
            stage_index = record.get("stage_index")
            stage = stages.get(stage_index) if _is_int(stage_index) else None
            if stage is None or stage.get("stage_id") != record.get("stage_id") or stage.get("pwm_command") != record.get("pwm_value"):
                errors.append(f"EVENT {record.get('record_id')} does not match a PWM_STAGE")

    samples_by_id = {
        r.get("sample_id"): r for r in records
        if isinstance(r, dict) and r.get("record_type") == "ADC_SAMPLE"
        and isinstance(r.get("sample_id"), str)
    }
    for record in records:
        if isinstance(record, dict) and record.get("record_type") == "DERIVED":
            for sample_id in record.get("input_sample_ids", []) if isinstance(record.get("input_sample_ids"), list) else []:
                sample = samples_by_id.get(sample_id) if isinstance(sample_id, str) else None
                if sample is None:
                    errors.append(f"DERIVED {record.get('record_id')} references unknown input sample {sample_id}")
                elif isinstance(sample.get("channel"), str) and sample.get("channel") in {"A2", "A3"}:
                    errors.append(f"DERIVED {record.get('record_id')} cannot use A2/A3 reference samples")

    status = manifest.get("status")
    if status == "completed":
        if len(stages) != 31 or set(stages) != set(range(31)):
            errors.append("completed package must contain exactly PWM_STAGE 0..30")
        elif any(stage.get("stage_status") != "completed" for stage in stages.values()):
            errors.append("completed package has a non-completed PWM_STAGE")
    elif status == "aborted":
        if len(stages) != 31 or set(stages) != set(range(31)):
            errors.append("aborted package must contain all 31 finalized PWM_STAGE records")
        if sum(stage.get("stage_status") == "aborted" for stage in stages.values()) > 1:
            errors.append("aborted package may contain at most one aborted stage")
    # incomplete deliberately permits missing stages; never synthesize not_reached rows.

    if raise_on_error and errors:
        raise ValueError("; ".join(errors))
    return errors
