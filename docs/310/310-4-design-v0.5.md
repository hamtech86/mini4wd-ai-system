# 310-4 Design Specification v0.5 — ADC acquisition and STOP/protocol reconciliation

> **Status:** Draft for command review. This document is design-only. It does not authorize firmware implementation, Python changes, compilation, upload, serial communication, motor energization, or a 310-second physical measurement. 310-5 is not authorized by this document.
>
> **Safety:** Hardware current-limit confirmation remains **NOT CONFIRMED** (`HARDWARE_CURRENT_LIMIT_CONFIRMED=false`). Software behavior is not evidence of independent hardware protection.

## 1. Purpose and scope

310-4 defines acquisition and protocol requirements for determining the ACS712 current-detection threshold and collecting evidence used in a winding-resistance estimate. The Python host owns the 310-second sequence. The Arduino provides command execution, acquisition, and telemetry. RawLog v2 is append-only and remains the authoritative record.

This version reconciles eight review findings from v0.4. It is a proposed design, not a formal acceptance.

### In scope
- 31 PWM stages, values 0 through 30, each 10 seconds; PWM 0 is the baseline.
- Independent ADC samples and their timestamps/context.
- Command correlation, STOP behavior, state definitions, framing and transmission scheduling.
- Mapping telemetry into accepted RawLog v2 records without mutating accepted contracts.

### Out of scope
- Any firmware/Python implementation or tests.
- Physical safety qualification, motor energization, real measurements, and transition to 310-5.
- Treating rotation as a failure: PWM 0–30 may rotate. Rotation is downstream analysis, not a 310-4 stop/failure condition.

## 2. Authority and invariants

1. Python owns stage order and duration; Arduino does not autonomously advance PWM stages.
2. STOP has priority over PWM commands. After STOP is latched, no delayed command may re-drive PWM.
3. A software timeout or state does not prove physical motor stop or independent protection.
4. Each ADC conversion is an individual sample; a multichannel scan is not one ADC_SAMPLE.
5. A0 and A1 remain independent. Never average them or substitute one for the other.
6. A4 and A5 remain independent raw voltage inputs. Do not replace them with calculated V4−V5.
7. A2 magnetic and A3 thermistor channels are references only; they do not control, stop, qualify, or produce 310-4 estimates.
8. RawLog records are append-only. Unknown calibration applicability is represented as `calibration_id=null`; do not invent calibration.
9. Any unresolved stage association is explicitly marked unresolved; do not silently assign by receipt time.
10. No formal acceptance or implementation authorization is implied by this draft or its publication.

## 3. Stage schedule

| Stage | PWM | Planned duration |
|---|---:|---:|
| 1 | 0 | 10 s |
| 2–31 | 1–30, sequential | 10 s each |

The nominal sequence is 310 seconds. The Python host’s stage timing follows the accepted 310-1 convention:
- Stage start is the host receipt time of the corresponding apply ACK.
- The prior stage’s end is the host send time of the next-stage command.
- `actual_duration_ms` is the host monotonic interval between those points.
- This is a host-defined command interval, **not** a claim of exact physical PWM-on duration.
- Device-side `t_apply` and ADC timestamps are supplementary evidence.

PWM is a direct Arduino `analogWrite(0..30)` value, not a percentage or normalized full-scale value.

## 4. Channel map and sample meaning

| ADC | Sensor | Raw signal role | Use |
|---|---|---|---|
| A0 | ACS712 #1 | `winding_current` | Primary current acquisition |
| A1 | ACS712 #2 | `brush_stability_observation` | Independent observation only |
| A2 | Magnetic sensor | `magnetic_reference` | Reference only |
| A3 | Thermistor | `thermistor_reference` | Reference only |
| A4 | V4 voltage input | `voltage_v4` | Independent raw voltage |
| A5 | V5 voltage input | `voltage_v5` | Independent raw voltage |

An ADC_SAMPLE represents exactly one conversion from one channel. Each conversion carries its own raw code, timestamp, sequence and stage context. A4/A5 may later be used to calculate a voltage difference, but their raw records remain intact.

## 5. Acquisition cadence — unified proposal

The v0.4 conflict is resolved in favor of the slower cadence proposed in its continuation:
- ADC scan 1 at time T.
- ADC scan 2 at T + 25 ms.
- Next scan 1 at T + 100 ms.
- Thus each channel is sampled at 20 Hz, and an ADC_BATCH is produced 10 times per second if each batch contains the two scans.

This cadence is a **proposal pending adequacy review**, not a verified capability or accepted requirement. Chapters 9, 11, 13 and 15 must all use this same cadence; no 25 ms/channel or 40 Hz/channel interpretation remains.

## 6. Immutable stage context

The host creates a unique `stage_context_id` for each applied stage and sends it with the PWM command. The Arduino associates the acknowledged applied context with subsequent conversions. Immediately before each conversion, the firmware snapshots the active context into that sample; it must not look up “current stage” later when serializing or when Python receives the sample.

The following identifiers have distinct meanings:
- `measurement_session_id`: one host measurement session.
- `command_id`: one command instance, used for command/ACK correlation.
- `stage_context_id`: immutable host stage context assigned to samples.
- `device_epoch_id`: identity of one Arduino boot epoch in RawLog.
- `device_sample_sequence`: per-device sample sequence, if available.

An apply ACK must echo the command correlation and applied stage context. Python persists the device-provided context unchanged and resolves it to a host `stage_id). If the context is absent, unknown, or contradictory, `stage_assignment=unresolved); never infer it solely from delayed host receipt time.

## 7. Proposed message framing and length accounting

All messages use the same framing rule: decoded message = fixed header + message payload + CRC; COBS-encode the decoded bytes; append one zero delimiter. Lengths below are **maximums** and must be confirmed against the final field widths and codec before implementation.

| Message | Decoded maximum | COBS maximum | Delimiter | Wire maximum |
|---|---:|---:|---:|---:|
| APPLY_ACK | 17 B | 18 B | 1 B | 19 B |
| STOP_ACK | 20 B | 21 B | 1 B | 22 B |
| STATUS | 17 B | 18 B | 1 B | 19 B |
| ERROR | 29 B | 30 B | 1 B | 31 B |
| ADC_BATCH | 193 B | 194 B | 1 B | 195 B |

These figures are a sizing proposal, not a frozen wire contract. The final protocol table must specify for every message: field order, field width, byte order, enum values, decoded length, COBS maximum, delimiter length, and total wire maximum. The prior ERROR inconsistency (28 vs 29 decoded bytes) is corrected here to 29 for budgeting; the implementation must not proceed until the exact field list is reconciled. STOP_ACK sizing must be recalculated after its independent status dimensions are frozen.

## 8. STOP request, acknowledgment and duplicate handling

### 8.1 STOP priority
STOP is accepted independently of the current PWM stage. On acceptance, the controller latches the stop condition, commands PWM 0, rejects later PWM apply requests for that session, and emits STOP_ACK. A delayed PWM command or retransmission cannot clear the latch or re-drive the motor.

### 8.2 Independent STOP_ACK dimensions
Do not overload one field with both requester/session relation and duplicate-history status. STOP_ACK carries separate status dimensions:

**Requester/session relation**
- `CURRENT_SESSION`
- `STALE_SESSION`
- `NO_SESSION`

**Request/history outcome**
- `NEW_RECORDED`
- `DUPLICATE_MATCH`
- `ID_CONFLICT`
- `HISTORY_FULL_UNRECORDED`
- `NOT_ESTABLISHED`

These enum labels are semantic names; their numeric codes and widths remain to be assigned in the final wire table. An accepted stop and a duplicate request are distinct outcomes. A stale-session STOP still requests a safe stop; it must not be discarded merely because its requester is stale.

### 8.3 Fixed four-entry history
- The STOP duplicate history has exactly four retained entries.
- Retained entries are not overwritten during the session.
- A STOP is always acted upon even when history is full.
- If a request cannot be recorded because history is full, return `HISTORY_FULL_UNRECORDED`; duplicate detection for that unrecorded request is not guaranteed.
- A retained key is the session/request identity tuple defined by the final protocol. Same key and same semantic request is a duplicate; same key with a different reason or incompatible payload is an ID conflict.
- History insertion order is deterministic. Full history does not evict an earlier entry.
- Python stores the exact received ACK bytes and outcome. A retransmission with byte-identical ACK is the same observed response. Python must not fabricate an earlier ACK or assume that a later response is identical if the device reports a changed history outcome.
- Python maintains one canonical result per request identity while retaining received protocol evidence as required by the accepted RawLog contract.

## 9. Boot identity, epoch and clock semantics

- `generation_counter64`: persistent monotonic boot-generation value, if the hardware persistence design supports it.
- `boot_id64`: unique identity for one boot epoch; its generation and uniqueness construction must be documented.
- `boot_challenge64`: challenge used in the handshake; it is not itself the boot identity.
- `epoch_token32`: HELLO_ACK correlation token. It is not a boot identity and may collide across epochs.
- RawLog `device_epoch_id` identifies the boot epoch and must use the accepted RawLog v2 type and representation. Do not substitute `epoch_token32) for it.

Python must distinguish boot epochs using the agreed boot identity. A 32-bit token collision alone must not cause samples from different boots to be merged. If the boot identity is unavailable or cannot be validated, mark epoch association unresolved rather than guessing.

## 10. Unified state machine and STOP eligibility

The state vocabulary is unified as follows:

| State | Meaning | STOP eligible |
|---|---|---|
| `BOOT` | Startup and initialization | Yes |
| `BOOT_ID_INVALID` | Boot identity cannot be established | Yes |
| `IDLE` | Initialized, no active session | Yes |
| `ARMED` | Session established, PWM not yet applied | Yes |
| `RUNNING` | PWM stage active | Yes |
| `STOP_LATCHED` | STOP accepted and latched; no further drive allowed | Yes, idempotent |
| `STOPPED` | Software sequence/controller has completed stop handling | Yes, idempotent |
| `FAULT` | General protocol/initialization/runtime fault | Yes |
| `FAULT_STOP` | Fault path with stop latch asserted | Yes, idempotent |

A transition into `STOP_LATCHED` or `FAULT_STOP` commands PWM 0. `STOPPED` means software handling completed; it is not physical stop confirmation. The final transition table must enumerate allowed transitions and invalid-command responses. A general `FAULT` must not be treated as equivalent to a confirmed physical stop; STOP remains eligible in every state.

## 11. ADC timestamp and sequence rules

Each sample includes:
- `device_sample_sequence`
- `device_timestamp_us_u32`
- `channel_code`
- `adc_raw)
- `stage_context_token`
- `acquisition_status`

Timestamp point is `conversion_midpoint`: take `micros()` immediately before and after `analogRead()), then record the midpoint. This is an estimate of conversion time, not the ADC sample-and-hold instant. On Uno, `micros()` has 4 µs granularity; it must not be described as 1 µs resolution.

The 32-bit microsecond clock wraps after approximately 71.6 minutes. Python unwraps timestamps within a validated `device_epoch_id`; modular deltas are reliable only when gaps are less than 2^31 µs (about 35.8 minutes). If the host starts observing after a wrap and cannot reconstruct boot-relative elapsed time, it must use a documented relative origin or mark `device_elapsed_us` unavailable/unresolved. It must not fabricate an absolute boot elapsed value.

## 12. Acquisition failure semantics

A failure is reported only when it is actually detectable:
- Invalid channel code or invalid acquisition precondition: detectable and reportable.
- A custom bounded ADC conversion routine that times out: detectable if such a routine is implemented and its timeout is specified.
- Standard Arduino `analogRead()` does not expose a per-conversion failure status. Do not claim a conversion timeout unless a bounded implementation exists.
- Sensor disconnection, floating input, or electrically implausible value is generally not distinguishable from a valid ADC code by `analogRead()` alone. It must not be labeled a proven acquisition failure without independent diagnostics.

ADC_BATCH `acquisition_status` therefore distinguishes successful conversion, known acquisition failure, and unavailable/unknown status. The RawLog mapping uses `adc_raw=null` only when no raw conversion value exists, and records `validity`/ `invalid_reason` according to the accepted schema.

## 13. RawLog v2 mapping

The accepted RawLog v2 envelope and field names are authoritative. This design does not redefine them. For each individual conversion, map to an ADC_SAMPLE record with the schema’s existing fields, including:
- identity/envelope fields (`schema_version`, `record_type`, `record_id`, `record_seq`, `log_id`, `measurement_session_id`, `recorded_at_utc));
- sample identity and channel fields (`sample_id`, `channel`, `sensor`, `signal_role`, `adc_raw`, `adc_resolution_bits`, `raw_unit=count`);
- device timing and context (`device_timestamp_us_u32`, `device_timestamp_point=conversion_midpoint`, `device_epoch_id`, `device_elapsed_us`, `device_sample_sequence`, `stage_context_id`, `stage_id`, `stage_assignment));
- calibration and quality (`calibration_id`, `validity`, `invalid_reason`).

This list is a mapping checklist, not permission to add fields. Preserve the exact accepted types, nullability, enums, and names from RawLog v2. Each conversion gets its own `host_received_at_utc` and `host_received_monotonic_ns` when those fields exist in the accepted schema. If a field is not part of that accepted schema, do not add it here.

## 14. TX scheduling, ownership and SRAM constraints

UART is 57600 bps, 8N1: theoretical payload ceiling is 5,760 bytes/s. Proposed average rates:
- ADC_BATCH: 1,940 B/s (10 batches/s × 194-byte encoded maximum; budgeting figure).
- STATUS: 180 B/s.
- APPLY_ACK: approximately 3.3 B/s.
- Total: approximately 2,123.3 B/s, about 36.9% of theoretical line capacity.

Average throughput does not prove bounded latency. Priority and nonblocking behavior are required:
1. STOP_ACK and fault/error response.
2. APPLY_ACK and session-critical STATUS.
3. ADC_BATCH.
4. Noncritical status/diagnostic traffic.

A frame must never be interleaved with another frame. TX must retain ownership of the frame/source buffer until every byte is accepted by the UART. Send only a bounded amount that fits `availableForWrite()`; return to the main loop and continue later. A call that can block while the hardware TX ring is full is not acceptable in the acquisition path. STOP handling must not wait for a complete ADC_BATCH transmission.

SRAM remains **unverified**. Proposed resources include ADC batch/sample storage, RX frame storage, TX frame state/storage, four STOP history entries, STATUS/ERROR state, HardwareSerial buffers and stack. The Uno has 2 KB SRAM; do not claim fit based on estimates. Before implementation, produce a compiler-backed static memory report and demonstrate that ADC acquisition and STOP remain responsive under worst-case transmission backlog. If the buffer strategy cannot meet this, reduce/stream the design without changing the accepted RawLog contract or silently dropping samples.

## 15. ADC_BATCH cadence and transport consistency

ADC_BATCH is emitted on the unified 100 ms batch interval (10 batches/s) and includes the two scans at offsets 0 and 25 ms. Its payload must preserve each individual conversion’s sequence, timestamp, channel, raw code, acquisition status and stage-context token.

If acquisition or transport falls behind, the device must not silently relabel samples, overwrite a buffer still owned by TX, or emit fabricated regular timestamps. Report a detectable loss/overflow condition with a defined counter/status. The exact loss record and counter encoding must be frozen in the wire contract before implementation.

## 16. Python compatibility and accepted interface

The accepted 310-3 interface includes `MessageCodec.encode_pwm(pwm:int)->bytes`, `encode_stop()->bytes`, `decode(payload:bytes)->object`; transport handles framing, partial/multiple frames, ACKs and unknown messages. Python owns the 310-second sequence.

The current interface does not by itself establish the required correlation and telemetry path. The design proposal is additive:
- transmit `stage_context_id) with PWM apply;
- correlate ACK using `command_id);
- receive ADC_BATCH telemetry;
- persist device-provided context and timestamp unchanged;
- resolve `stage_id) in Python;
- preserve the existing `send_pwm(pwm)` behavior and existing tests until an explicitly reviewed compatibility change is approved.

The current `record_adc_sample()` behavior must not assign late telemetry using whichever stage is active at receipt time. This v0.5 does not authorize Python changes.

## 17. Acceptance evidence required before implementation

A future review must receive, at minimum:
1. Final byte-exact message definitions, including all lengths and enum values.
2. One coherent state transition and STOP eligibility table.
3. STOP history examples: first request, exact duplicate, ID conflict, stale session, and full history.
4. Boot identity/epoch examples across reset and token collision.
5. Sample traces demonstrating individual timestamps and immutable stage context across a stage boundary.
6. Explicit loss/overflow semantics and bounded TX scheduler behavior.
7. Compiler-backed SRAM/stack budget and proof of nonblocking acquisition/STOP handling.
8. Clear distinction between detectable ADC acquisition failures and electrical/sensor anomalies.
9. Confirmation that the RawLog mapping matches accepted 310-1/2 schemas without adding or mutating fields.
10. A review disposition for all eight v0.4 findings.

No real-hardware test, motor energization, upload, or 310-5 transition is permitted by this draft. Those require separate explicit authorization.

## 18. v0.4 review disposition

| Review item | v0.5 disposition |
|---|---|
| 1. ADC cadence conflict | Unified to proposed 20 Hz/channel; adequacy remains pending |
| 2. STOP_ACK status conflict | Requester/session and history outcomes separated |
| 3. Four-entry STOP history | Fixed non-overwriting history; full behavior specified |
| 4. boot_id vs epoch_token | Roles separated; RawLog epoch remains boot identity |
| 5. State vocabulary | One table; STOP eligible in every state |
| 6. Frame lengths | One length convention and budget table; exact byte table still required |
| 7. SRAM/TX | Ownership and nonblocking requirements stated; SRAM not verified |
| 8. Timestamp/failure | Midpoint semantics, wrap limits and detection boundary specified |

**Decision requested:** review this integrated v0.5 as a design proposal. Do not treat it as accepted, implementation-ready, or authorization for hardware activity.
