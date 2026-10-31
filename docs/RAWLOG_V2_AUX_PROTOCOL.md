# RawLog v2 AUX protocol contract (draft 2)

Status: implementation contract for host-side parser; firmware adoption is a separate change.
Compatibility authority: Issue #35. The existing `DATA` record remains exactly 26 fields and is not extended or reinterpreted.

## 1. Separation of layers

- Arduino emits one AUX record for each individual ADC conversion. It records raw ADC counts and the conversion timestamp; it does not calculate resistance, voltage difference, brush stability, statistics, or quality scores.
- Python validates and preserves the original record, then performs channel/time alignment and all derived calculations.
- Existing `INFO`, command-response, and 26-field `DATA` records retain their current meanings.
- AUX is additive and must not be fed to the DATA parser or Measurement control path.

## 2. Wire format

ASCII comma-separated line, UTF-8, terminated by LF or CRLF:

```
AUX,2,<session_id>,<sequence>,<phase>,<direction>,<pwm>,<run_state>,<channel>,<adc_raw>,<timestamp_us>
```

Exactly 11 fields, in this order:

| Index | Field | Type / allowed value |
|---:|---|---|
| 0 | record_type | literal `AUX` |
| 1 | protocol_version | literal integer `2` |
| 2 | session_id | non-empty token: letters, digits, dot, underscore, hyphen |
| 3 | sequence | unsigned 32-bit integer; same scan/frame sequence across channels in one acquisition cycle |
| 4 | phase | non-empty token; firmware phase identifier, e.g. `WINDING` or `BRUSH` |
| 5 | direction | `FWD`, `REV`, or `STOP` |
| 6 | pwm | integer 0..255 |
| 7 | run_state | non-empty token describing the firmware output/control state |
| 8 | channel | exactly `A0`, `A1`, `A4`, or `A5` |
| 9 | adc_raw | integer 0..1023 for the current Arduino Uno ADC |
| 10 | timestamp_us | unsigned 32-bit `micros()` value, captured for this individual ADC conversion |

No derived/calibrated engineering values are sent in AUX. In particular, do not transmit calculated A0/A1 current, A4-A5 voltage, resistance, or stability metrics in place of raw ADC counts.

The firmware must emit a separate record for each channel conversion. Do not imply that four sequential ADC reads share one timestamp. The `sequence` groups conversions belonging to the same acquisition cycle; `timestamp_us` preserves their actual order and spacing.

## 3. Fixed channel meaning

| Channel | Meaning | Python use |
|---|---|---|
| A0 / ACS712 #1 | winding measurement current signal | winding analysis input |
| A1 / ACS712 #2 | brush evaluation signal | separate brush analysis input only |
| A4 | motor voltage sense | paired with A5 by acquisition time |
| A5 | motor voltage sense | paired with A4 by acquisition time |

A0 and A1 must never be averaged or substituted for one another. Direction-aware voltage-difference interpretation is performed in Python from the A4/A5 readings and the direction field.

## 4. Timestamp and sequence rules

- `timestamp_us` is the raw unsigned 32-bit Arduino microsecond counter at the individual ADC conversion.
- It wraps modulo 2^32. Preserve the raw value unchanged. Python may create a separate unwrapped timeline after ordering records by session and sequence; never overwrite the raw timestamp.
- A session boundary resets sequence/timestamp interpretation. Session IDs must not be reused within a captured RawLog.
- Sequence is unsigned 32-bit and may wrap. Consumers must use modular ordering and must not assume it is globally unique.
- The firmware should emit channel records in acquisition order. Missing channel conversions are represented by absence plus a detectable sequence/channel gap; do not invent an ADC value.
- No maximum allowable A4/A5/A0 skew is fixed by this wire contract. Python configuration/analysis policy owns that threshold and must retain observed skew and rejection reason.

## 5. RawLog v2 storage boundary

The serial wire record and persisted RawLog record are separate schemas.

The host parser returns:
- typed validated fields,
- the exact original line (without line terminator) for traceability,
- protocol version and record type.

RawLog v2 stores AUX as an additive record collection (JSONL is the proposed representation), retaining the original wire line and typed fields.

The wire format's stable sample identity is derived by Python as
`<session_id>:<sequence>:<channel>`. It is not added to the serial wire
record and does not replace the raw sequence or timestamp. The host storage
layer rejects duplicate sample identities within one RawLog rather than
silently overwriting or merging them. Derived records reference these IDs.

Derived records are stored separately and include at minimum:
- derived metric name,
- formula/algorithm identifier and version,
- input sample IDs,
- result value and unit (nullable when invalid),
- validity status,
- rejection/invalid reason.

### Implemented local sidecar layout (draft 2)

For a registered local RawLog body such as `MOTOR-000123.log`, the host may add:

- `MOTOR-000123.aux.jsonl`: one JSON object per validated AUX record. Each object contains `record_type=AUX`, all typed wire fields, and `raw_line`.
- `MOTOR-000123.derived.jsonl`: one JSON object per derived result, separate from raw AUX.
- `MOTOR-000123.manifest.json`: `schema=mini4wd.rawlog.v2`, `log_id`, the application `measurement_session_id`, unique firmware `aux_session_ids`, immutable `raw_body` reference, AUX sidecar name/count, parse diagnostics, Derived sidecar name/count, and Derived status.

A manifest is created only when AUX or explicitly supplied Derived records exist. Existing v1 logs without sidecars remain v1 and are not backfilled or reclassified. The original raw body, including its received line endings, is never rewritten by sidecar registration.

Each Derived record requires `metric`, `algorithm_id`, `algorithm_version`, `input_sample_ids`, `value`, `unit`, `valid`, and `invalid_reason`. A valid result must contain a finite numeric value and no invalid reason. An invalid result must carry a non-empty reason; its value may be null. This storage API does not select or execute any analysis formula.

This is the local filesystem persistence contract only. Remote GitHub synchronization and UI presentation of sidecars remain separate work. Do not silently change the existing RawLog v1 26-column DATA record or convert old v1 logs to v2.

## 6. Python timestamp alignment behavior

The host-side alignment helper preserves serial arrival order within each
session and creates an unwrapped timestamp as a separate derived field:

- The raw `timestamp_us` remains the original uint32 value.
- A decrease larger than half the uint32 range is treated as the normal
  `micros()` rollover and adds 2^32 to the unwrapped timeline.
- A smaller backwards movement is rejected as an ordering error; the host
  does not silently sort or guess the intended order.
- Timeline state is independent for each session ID.
- Samples are grouped by `(session_id, sequence)`. Duplicate channels in one
  acquisition cycle are rejected.
- A4/A5 skew is recorded as signed `A5 timestamp - A4 timestamp` in
  microseconds. No maximum skew threshold is imposed by this helper.
- A missing A4 or A5 produces an invalid/incomplete pair with an explicit
  reason; no ADC value is substituted.
- Phase, direction, PWM, and run-state disagreement within one cycle makes
  that cycle's A4/A5 pair invalid.
- A0 and A1 remain separate channel samples. Their values are not averaged or
  substituted for each other.

The helper performs alignment only. It does not convert ADC counts to volts or
amperes, calculate resistance, infer brush stability, or decide whether a
measured skew is physically acceptable.

## 7. Error handling

Reject malformed AUX records: wrong field count/type/version, empty tokens, unknown channel/direction, non-integer values, out-of-range ADC/PWM/sequence/timestamp. Preserve rejected original text in the transport capture/error stream with a parse error; do not silently discard it and do not turn it into a DATA frame.

No invalid sample is replaced with zero or a previous sample.

## 8. Example

```
AUX,2,sess_20261031_0001,42,WINDING,FWD,0,MEASURE,A0,514,123456
AUX,2,sess_20261031_0001,42,WINDING,FWD,0,MEASURE,A4,520,123463
AUX,2,sess_20261031_0001,42,WINDING,FWD,0,MEASURE,A5,498,123471
```

These are three distinct conversions in one acquisition cycle. They are raw ADC counts, not amperes or volts.

## 9. Implementation sequence

1. Host-side strict parser and unit tests (implemented).
2. Serial dispatch in the active SerialController (implemented; CI pending).
3. Local AUX/Derived sidecars and manifest with v1 non-reclassification tests (implemented; CI pending).
4. Implemented host-side stable sample IDs, per-session timestamp unwrapping, cycle grouping, and signed A4/A5 skew reporting without inventing a skew threshold.
5. Implement firmware emission against the approved contract; Arduino-side changes remain acquisition/timestamp/output only.
6. Integration tests, then compile and physical-device validation as separate gates.
