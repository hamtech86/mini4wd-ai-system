# RawLog v2 AUX protocol contract (draft 1)

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

RawLog v2 stores AUX as an additive record collection (JSONL is the proposed representation), retaining the original wire line and typed fields. Derived records are stored separately and include at minimum:
- derived metric name,
- formula/algorithm identifier and version,
- input sample IDs,
- result value and unit (nullable when invalid),
- validity status,
- rejection/invalid reason.

The exact enclosing RawLog v2 manifest/session layout is not finalized by this document. Do not silently change the existing RawLog v1 26-column DATA record or convert old v1 logs to v2.

## 6. Error handling

Reject malformed AUX records: wrong field count/type/version, empty tokens, unknown channel/direction, non-integer values, out-of-range ADC/PWM/sequence/timestamp. Preserve rejected original text in the transport capture/error stream with a parse error; do not silently discard it and do not turn it into a DATA frame.

No invalid sample is replaced with zero or a previous sample.

## 7. Example

```
AUX,2,sess_20261031_0001,42,WINDING,FWD,0,MEASURE,A0,514,123456
AUX,2,sess_20261031_0001,42,WINDING,FWD,0,MEASURE,A4,520,123463
AUX,2,sess_20261031_0001,42,WINDING,FWD,0,MEASURE,A5,498,123471
```

These are three distinct conversions in one acquisition cycle. They are raw ADC counts, not amperes or volts.

## 8. Implementation sequence

1. Host-side strict parser and unit tests (this branch).
2. Add a serial dispatch path that recognizes AUX without changing DATA parsing/control behavior.
3. Define and test RawLog v2 persistence/manifest with v1 regression fixtures.
4. Implement firmware emission against this contract; Arduino-side changes remain acquisition/timestamp/output only.
5. Integration tests, then compile and physical-device validation as separate gates.
