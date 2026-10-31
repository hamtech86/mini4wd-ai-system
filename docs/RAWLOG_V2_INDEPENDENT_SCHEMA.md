# RawLog v2 Independent Record Schema

Status: draft for coordinator review, 2026-10-31  
Authority: Issue #35. Implementation work: Issue #170. Measurement workflow: Issue #174.

## 1. Compatibility boundary

- RawLog v2 is a new canonical format. It is not a 26-column CSV and does not preserve v1 column positions, row layout, or storage compatibility.
- RawLog v1 is legacy. Preserve existing v1 files byte-for-byte; do not rewrite, migrate, infer-convert, or reclassify them.
- No v1-to-v2 compatibility layer is required.
- Independence of format does **not** mean loss of information. V2 must retain every measurement item represented by the former RawLog, using named fields, and add the additional measurement evidence needed by current workflows.
- The serial wire protocol, Python in-memory model, and persisted v2 schema are separate contracts. Do not require Arduino to emit JSON.

## 2. File organization

One registered measurement is one RawLog v2 package:

```text
<log_id>/
  manifest.json
  records.jsonl
```

- `manifest.json` identifies schema/version, log ID, application measurement session, firmware/device identity, motor/battery instance association, acquisition start/end, and record counts.
- `records.jsonl` is append-only during capture. Each line is one independent JSON object. Preserve original received serial text in a transport-capture field or linked transport record when traceability is needed.
- Do not split AUX into an unrelated optional add-on that makes the main RawLog appear complete when the remaining measurement fields are absent. ADC conversions, measurement snapshots, events, calibration, and derived results belong to the same logical RawLog package.
- A capture interrupted by STOP, disconnect, timeout, or application exit remains a valid incomplete RawLog. Mark its final status and reason; never mark unobserved stages complete.

## 3. Common record envelope

Every JSONL object contains:

| Field | Type | Rule |
|---|---|---|
| schema | string | `mini4wd.rawlog.v2` |
| record_type | string | `SESSION`, `MEASUREMENT`, `ADC_SAMPLE`, `CALIBRATION`, `EVENT`, or `DERIVED` |
| log_id | string | Stable RawLog identity |
| measurement_session_id | string | Application-created session identity |
| record_id | string | Unique within this RawLog |
| sequence | integer | Monotonic record sequence within this RawLog |
| elapsed_time_ms | integer | Monotonic elapsed time from session start |
| recorded_at | string | ISO-8601 timestamp with timezone |

A record must not silently omit a required field. Values not available must be represented explicitly as `null` together with an availability/invalid reason; never substitute zero or a previous reading.

## 4. Required record types

### 4.1 SESSION

Exactly one opening SESSION record describes the acquisition:
- application, firmware version/build, device type/model/device ID;
- motor/battery instance association where applicable;
- local start time and monotonic start reference;
- measurement plan identifier and parameters;
- RawLog v2 schema version.

A final SESSION summary or manifest records completion status: `COMPLETE`, `STOPPED`, `INTERRUPTED`, or `FAULTED`, end time, and reason.

### 4.2 MEASUREMENT — full RawLog measurement item set

A MEASUREMENT record is the named-field snapshot for a measurement cycle. It must represent all former RawLog measurement items below; the names and structure are v2 names, not v1 CSV columns.

| V2 field | Type / unit | Former measurement meaning |
|---|---|---|
| device_model | string | Device model |
| instance_id | string | Firmware/device instance identifier (not DB motor instance ID) |
| elapsed_time_ms | integer | Elapsed measurement time |
| raw_acs1 | integer or null | ACS712 #1 raw ADC |
| raw_acs2 | integer or null | ACS712 #2 raw ADC |
| current1_a | number or null | Current sensor 1 converted current |
| current2_a | number or null | Current sensor 2 converted current |
| voltage1_v | number or null | A4 / VM1 voltage |
| voltage2_v | number or null | A5 / VM2 voltage |
| motor_voltage_v | number or null | Signed raw difference V4 - V5 |
| pwm | integer | PWM command 0..255 |
| direction | string | FWD, REV, or STOP |
| state | string | Firmware output/control state |
| current_avg_a | number or null | Average current |
| power_w | number or null | Power |
| current_ripple_a | number or null | Current ripple |
| voltage_ripple_v | number or null | Voltage ripple |
| peak_power_w | number or null | Peak power |
| peak_current_a | number or null | Peak current |
| peak_voltage_v | number or null | Peak voltage |
| peak_pwm | integer or null | PWM at peak |
| brush_peak_current_a | number or null | Brush peak current |
| raw_magnetic | integer or null | Magnetic sensor raw ADC |
| magnetic_level | number or null | Magnetic sensor converted value |
| motor_temperature_c | number or null | Motor temperature |

All listed keys must be present in each MEASUREMENT record. If a sensor/value is unavailable in a particular device or phase, use null and include `unavailable_fields` entries with a reason; do not silently omit the field. If a value is calculated by Python rather than acquired by firmware, identify the calculation in a DERIVED record and link it; do not fabricate it in the raw measurement record.

V2 may add named fields without changing the meaning of existing ones. Unit suffixes are mandatory for engineering values.

### 4.3 ADC_SAMPLE — individual conversion evidence

One ADC_SAMPLE record represents exactly one ADC conversion. Required fields:
- channel: A0, A1, A4, or A5;
- adc_raw: integer 0..1023 for Arduino Uno;
- timestamp_us: raw uint32 micros() captured for that conversion;
- acquisition_sequence: identifier grouping conversions from one scan cycle;
- phase, direction, pwm, run_state at acquisition;
- conversion status / invalid reason where applicable.

Do not give four sequential conversions one shared timestamp. Preserve raw timestamp unchanged; Python may create a separate unwrapped timestamp. A0 (winding current) and A1 (brush observation) are independent and must never be averaged or substituted. A4/A5 pairing and direction-aware voltage interpretation are performed in Python.

### 4.4 CALIBRATION

Store calibration snapshots/changes as explicit records:
- sensor/channel and calibration ID/version;
- raw calibration inputs, zero offset, scale/gain, unit;
- validity interval or acquisition sequence boundary;
- source and status (measured, configured, unverified).
Never silently apply a default calibration when no approved calibration is available. Raw ADC values remain immutable.

### 4.5 EVENT

Record state and workflow events, including:
- measurement started; PWM stage started/completed; stage command sent/acknowledged;
- STOP, PAUSE, emergency STOP, communication loss/recovery, timeout, fault;
- user rotation observation: `NO_ROTATION`, `ROTATION`, `UNKNOWN`;
- label entry time, target stage/PWM interval, and optional note;
- any external reference observation (e.g. phone RPM) with source and explicit non-authoritative status.

Rotation-positive records are retained and used for comparison against no-rotation data. Until an automatic rotation classifier is validated, user visual observation is the reference label. Rotation-positive and unknown intervals are excluded from pre-rotation winding-resistance candidate evaluation, but not deleted from the RawLog.

### 4.6 DERIVED

Derived results are separate records and include:
- metric, algorithm_id, algorithm_version;
- input record/sample IDs;
- value and unit (nullable if invalid);
- valid flag and invalid_reason;
- applicable calibration IDs and policy/configuration references.

Never mix derived results into raw ADC evidence or overwrite source records.

## 5. 310-second PWM sweep metadata

For the winding micro-current detectability workflow:
- Python is the only 310-second sweep orchestrator.
- Python sends PWM 0 through 30 in ascending order, holding each stage for 10 seconds (31 stages, 310 seconds total). PWM 0 is output-off baseline.
- PWM 1..9 are priority candidates for micro-current evaluation, but the full 0..30 sweep is retained for optimum-candidate exploration.
- Arduino receives each command, applies safety checks, controls the requested output, and emits acquisition evidence. Arduino does not run a 310-second stage scheduler.
- Record requested stage, command/acknowledgement times, actual observed PWM/state, stage start/end, early stop, and completion status.
- The user may enter a visual rotation label for a stage or interval. Retain all labels and raw data.

## 6. Responsibility boundaries

- Arduino: raw sensor acquisition, individual conversion timestamps, hardware output execution, firmware/device state, and independent hardware safety response.
- Python: sweep orchestration, command sequencing, session lifecycle, complete v2 package creation, field validation, time alignment, calibration application, engineering conversions, statistics, quality gates, rotation-label entry, and candidate selection.
- Python must not claim physical output/stop success from command-write success alone.
- Firmware and Python changes must preserve existing Benchmark/TuneBasic/ARM/STOP behavior unless a separately approved change says otherwise.

## 7. Validation gates

1. Schema validation: all record types, required fields, null/unavailable semantics, units, IDs, sequence, and event ordering.
2. Completeness validation: every former RawLog measurement item is represented; no 4-channel-only truncation.
3. Host tests: stage boundaries, stop/interruption, communication loss, timestamp wrap, missing/duplicate ADC samples, rotation labels, and incomplete-session handling.
4. Regression tests: Benchmark/TuneBasic/ARM/STOP behavior; preserve v1 files byte-for-byte without requiring v1/v2 compatibility.
5. Arduino compile/HEX validation.
6. Physical upload and motor energization are separate gates requiring explicit user authorization.

CI success does not prove physical ADC detectability, current calibration, winding resistance validity, or motor rotation classification.
