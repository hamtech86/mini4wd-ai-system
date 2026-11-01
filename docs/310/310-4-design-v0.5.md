# 310-4 Design Specification v0.5 — Re-submission (review corrections)

> **Status: Draft / command review only.** This is a design proposal. It does not authorize firmware or Python implementation, compilation, upload, serial communication, motor energization, a 310-second physical measurement, formal acceptance, or transition to 310-5.
>
> **Safety gate:** `HARDWARE_CURRENT_LIMIT_CONFIRMED=false`. Software state, STOP acknowledgement, and PWM=0 are not proof of physical stop or independent hardware protection.

## 1. Purpose, authority and scope

310-4 defines acquisition and communication requirements for the PWM 0–30, 310-second measurement. Python owns the 31-stage sequence (PWM 0 through 30, 10 seconds each); Arduino executes explicit commands and acquires raw samples. The purpose is to characterize the ACS712 #1 detection threshold and collect evidence relevant to winding-resistance measurement. This document does not define a resistance formula or declare any current value valid for resistance calculation.

Issue #35 is the project specification authority. Issue #170 defines the Arduino/Python/RawLog v2 contract workstream; Issue #174 defines the measurement purpose and constraints. This document may propose a detailed implementation contract for review but cannot override those authorities or convert their unresolved items into accepted requirements.

### In scope
- Independent per-conversion raw ADC acquisition and timestamps.
- PWM-stage context propagation and command correlation.
- Message framing, STOP behavior, state transitions, loss reporting and scheduling.
- Mapping serial telemetry into the separately defined RawLog v2 format.

### Out of scope
- Firmware/Python implementation, tests, compilation, upload, serial activity, and real hardware measurements.
- Physical safety qualification and 310-5.
- Rotation detection as a 310-4 failure or automatic stop condition. PWM 0–30 may rotate; rotation is a separately recorded observation/analysis label.

## 2. Binding measurement and channel rules

| Input | Sensor / signal | Meaning | Permitted role |
|---|---|---|---|
| A0 | ACS712 #1 | Winding-current raw signal | Sole current input for winding-current conversion and winding-resistance analysis |
| A1 | ACS712 #2 | Independent brush-stability observation | Never average with, replace, or interpolate A0 |
| A4 | V4 | Independent voltage raw signal | Preserve raw conversion; interpret in Python according to direction and TERMINAL/INPUT mode |
| A5 | V5 | Independent voltage raw signal | Preserve raw conversion; interpret in Python according to direction and TERMINAL/INPUT mode |
| A2 | Magnetic sensor | Reference observation | Record/display only; no control, stop, quality, eligibility or required-analysis use without separate approval |
| A3 | Thermistor | Reference observation | Record/display only; no control, stop, quality, eligibility or required-analysis use without separate approval |

A0/A1 are independent physical signals. Do not average them or treat A1 as an A0 substitute. A4/A5 are independently recorded; do not replace them with V4−V5. A2/A3 cannot drive PWM, ARM, STOP, continuation, fault classification, measurement acceptance or derived estimates before explicit use-specific approval.

Each ADC conversion is one sample. A scan or batch is only a transport grouping; it is not one ADC_SAMPLE.

## 3. Sequence and timing ownership

There are 31 host-controlled stages: PWM 0, 1, …, 30 in ascending order, each planned for 10 seconds (310 seconds nominal). PWM 0 is the output-off baseline. PWM is a direct Arduino `analogWrite(0..30)` value, not a percentage.

The accepted 310-1 host timing convention applies:
- Stage start = host monotonic time when the matching apply ACK is received.
- Previous stage end = host monotonic time immediately before the next-stage command is sent.
- `actual_duration_ms` = that host interval.
- This is a host command interval, not a claim of exact physical PWM-on time.
- Device apply time and per-conversion timestamps are supplementary device evidence.

Arduino must not implement an autonomous 310-second sequencer. STOP, communication loss or fault must not cause uncompleted stages to be marked complete.

## 4. ADC sample structure and cadence candidate

### 4.1 Individual conversion fields

Each sample in the serial ADC_BATCH contains the following 14-byte sample unit, in this exact order:

| Offset | Field | Width | Encoding |
|---:|---|---:|---|
| 0 | `sample_sequence` | 2 B | uint16 little-endian, increments per attempted conversion |
| 2 | `timestamp_us_u32` | 4 B | uint32 little-endian, micros() midpoint |
| 6 | `channel_code` | 1 B | 0=A0, 1=A1, 2=A2, 3=A3, 4=A4, 5=A5 |
| 7 | `adc_raw` | 2 B | uint16 little-endian; 0–1023 for 10-bit ADC |
| 9 | `stage_context_token` | 2 B | uint16 little-endian; 0 means unresolved/no context |
| 11 | `acquisition_status` | 1 B | 0=OK, 1=PRECONDITION_INVALID, 2=CONVERSION_TIMEOUT, 3=NOT_ACQUIRED |
| 12 | `sample_flags` | 2 B | uint16 little-endian; v1 must be zero; reserved bits must be zero |

The 14-byte unit is fixed-size. A conversion that was attempted but has no valid raw code uses `adc_raw=0xFFFF` and a nonzero status; zero is a valid ADC value and must not mean missing. `sample_sequence` increments for every attempted conversion, including a failed conversion, and wraps modulo 65536. A batch never renumbers samples.

### 4.2 Batch payload

The fixed ADC_BATCH payload is 173 bytes:
- `batch_sequence`: uint16 (2 B)
- `batch_flags`: uint8 (1 B)
- `sample_count`: uint8 (1 B), exactly 12 in a complete batch
- `loss_counter_snapshot`: uint8 (1 B), low 8 bits of the cumulative loss counter; full counter is reported in STATUS
- 12 sample units × 14 B = 168 B

Total payload = 5 + 168 = 173 B. A partial batch is not permitted in protocol v1. If fewer than 12 sample attempts are available, do not emit a malformed partial ADC_BATCH; report the missing attempts through sequence gaps and STATUS loss fields.

### 4.3 Cadence

The only cadence under consideration is:
- Scan 1 begins at T.
- Scan 2 begins at T + 25 ms.
- Next Scan 1 begins at T + 100 ms.
- Each channel is therefore sampled at 20 Hz; one 12-sample batch is emitted per 100 ms, i.e. 10 batches/s.

This is a **candidate cadence, not an accepted requirement**. The sample order within each scan is A0, A1, A4, A5, A2, A3. The time of each conversion is its own timestamp; channel order does not imply simultaneous sampling.

### 4.4 Cadence adequacy boundary

At 20 samples/s per channel, Nyquist frequency is 10 Hz. This cadence can characterize slow stage-to-stage or quasi-DC trends if the analog signal is sufficiently settled and if the acquisition phase/filtering are characterized. It cannot resolve PWM-frequency ripple, fast commutation transients, or waveform shape above 10 Hz. ACS712 bandwidth and motor/PWM dynamics can be far above this limit; no claim is made that 20 Hz captures them.

For the stated threshold/resistance purpose, 20 Hz may be adequate only for a deliberately defined low-frequency statistic (for example, a stable-window mean/dispersion computed in Python) after settling and aliasing are evaluated. It is not sufficient evidence for peak/ripple/current-transient characterization. The analog front-end filter, PWM frequency, expected signal bandwidth, settling time, threshold decision statistic, and required uncertainty have not yet been specified. Therefore 20 Hz remains a candidate and must not be frozen until those inputs and a sampling/aliasing analysis are reviewed. No firmware sampling-rate change is authorized here.

## 5. Stage-context identity and mapping

Python creates a globally unique `stage_context_id` for each stage as a UUID string in RawLog v2. The wire protocol does not transmit that full string in every sample. Instead:

1. Before a stage command, Python allocates a nonzero uint16 `stage_context_token`. Token values are unique within a `measurement_session_id`; do not reuse a token in that session. With 31 stages, tokens 1–31 are sufficient.
2. Python durably records a context-map entry before sending the command: `measurement_session_id`, token, UUID `stage_context_id`, `stage_id`, intended PWM and command_id.
3. PWM_SET carries both the uint16 token and the host command_id. APPLY_ACK echoes both.
4. Immediately before every ADC conversion, Arduino snapshots the currently applied token into that sample. It does not look up the active stage later during batching or transmission.
5. Python resolves token using the map scoped by both measurement_session_id and device_epoch_id, then writes the mapped UUID to RawLog. It never writes the 16-bit token into the RawLog UUID field.
6. Unknown token, token zero, mismatched session/epoch, or contradictory ACK/sample mapping produces `stage_assignment=unresolved`; no nearest-time inference is allowed.

A device reboot invalidates the current command/session association. A new session and new token map are required after handshake. A token collision in another session or boot epoch cannot alias a prior context because the lookup namespace includes session and device epoch. The mapping table and the original wire token are retained as separate data; the token alone is not a globally unique stage_context_id.

## 6. Message framing and exact byte lengths

### 6.1 Framing rule

All protocol messages use:
- 17-byte fixed common header.
- Message-specific payload.
- 2-byte CRC-16/CCITT-FALSE, little-endian, calculated over header plus payload.
- COBS encoding of the complete decoded message.
- One zero delimiter byte after the COBS frame.

COBS maximum for a decoded frame of N bytes is N + ceil(N/254). All current frames are below 254 bytes, so the COBS maximum is N+1. Wire maximum is COBS maximum + one delimiter.

The 17-byte common header field allocation for this candidate is: magic uint16 (2), protocol_version uint8 (1), message_type uint8 (1), flags uint8 (1), measurement_session_tag uint32 (4), device_epoch_tag uint32 (4), command_id uint32 (4). Multi-byte integers are little-endian. The tags are correlation values only; they do not replace the full RawLog session UUID or boot identity.

### 6.2 Message payloads and lengths

| Message | Payload definition | Payload | Decoded (17 + payload + 2 CRC) | COBS max | Delimiter | Wire max |
|---|---|---:|---:|---:|---:|---:|
| PWM_SET | pwm uint8 + stage_context_token uint16 | 3 B | 22 B | 23 B | 1 B | 24 B |
| APPLY_ACK | result uint8 + applied_pwm uint8 + stage_context_token uint16 | 4 B | 23 B | 24 B | 1 B | 25 B |
| STOP_REQ | stop_reason uint8 + stop_request_id uint16 | 3 B | 22 B | 23 B | 1 B | 24 B |
| STOP_ACK | requester_relation uint8 + request_outcome uint8 + latched_state uint8 | 3 B | 22 B | 23 B | 1 B | 24 B |
| STATUS | state uint8 + active_pwm uint8 + active_context_token uint16 + loss_counter uint32 + last_sample_sequence uint16 | 10 B | 29 B | 30 B | 1 B | 31 B |
| ERROR | error_code uint8 + offending_message_type uint8 + detail_code uint16 + related_command_id uint32 | 8 B | 27 B | 28 B | 1 B | 29 B |
| ADC_BATCH | payload defined in §4.2 | 173 B | 192 B | 193 B | 1 B | 194 B |

These are proposed v1 byte definitions for review, not accepted production wire compatibility. The header tags must be initialized by HELLO/handshake and validated before PWM_SET. CRC failure, malformed COBS, unknown protocol version or invalid reserved bits must not result in PWM application.

### 6.3 ADC_BATCH arithmetic and throughput reconciliation

The ADC_BATCH calculation is:
- common header: 17 B
- 12 samples × 14 B: 168 B
- fixed batch payload: 5 B
- CRC: 2 B
- decoded total: 17 + 168 + 5 + 2 = **192 B**
- COBS maximum: 192 + ceil(192/254) = **193 B**
- delimiter: 1 B
- wire maximum: **194 B**

At 10 batches/s, ADC_BATCH maximum traffic is 1,940 wire B/s. Do not use 194 as decoded size or 193 as wire size.

## 7. STOP request, ACK and duplicate history

### 7.1 STOP semantics

STOP is accepted in every defined state. On receipt, controller latches stop, requests PWM=0, invalidates the active ARM permission and rejects every later nonzero PWM_SET until a new explicitly authorized session/ARM sequence. A delayed command cannot clear STOP or re-drive the motor. A stale-session STOP is still treated as a safety stop request; session staleness affects the ACK classification, not whether the stop action is attempted.

### 7.2 STOP_ACK fields and enum codes

STOP_ACK payload is exactly three bytes as defined in §6.2:

**Byte 0 — requester_relation**
- 0 = CURRENT_SESSION
- 1 = STALE_SESSION
- 2 = NO_SESSION

**Byte 1 — request_outcome**
- 0 = NEW_RECORDED
- 1 = DUPLICATE_MATCH
- 2 = ID_CONFLICT
- 3 = HISTORY_FULL_UNRECORDED
- 4 = NOT_ESTABLISHED

**Byte 2 — latched_state**
- 0 = STOP_LATCHED
- 1 = FAULT_STOP
- 2 = STOPPED

All other enum values are invalid and reserved. The fields represent independent dimensions: requester/session relation is not duplicate status. STOP_ACK decoded length is 17 + 3 + 2 = 22 B; COBS maximum 23 B; delimiter 1 B; wire maximum 24 B.

### 7.3 Four-entry history

History contains exactly four fixed entries per device boot epoch. Each entry stores session tag, stop_request_id, stop_reason, and semantic request fingerprint. Entries are inserted in first-free slot order and never overwritten during that boot epoch.

- First request with free slot: perform stop and record; outcome NEW_RECORDED.
- Same session tag + request ID + same reason/fingerprint in retained history: stop remains latched; outcome DUPLICATE_MATCH.
- Same session tag + request ID but different reason/fingerprint: stop remains latched; outcome ID_CONFLICT.
- No free slot and request not found: perform stop; outcome HISTORY_FULL_UNRECORDED. No duplicate-detection guarantee is made for this unrecorded request.
- A retained entry is not evicted to make room. History is cleared only on a new boot epoch; boot identity distinguishes the new epoch.
- A stale session request is still processed as STOP. If it matches retained history, report the matching history outcome; requester_relation independently reports STALE_SESSION.

Python stores every received STOP_ACK byte-for-byte as protocol evidence. For a request identity, Python preserves the first response as the canonical initial response and stores later retransmission responses separately. A later response with a different outcome is not silently rewritten to look like the first response. The Python log records that history-full responses cannot establish duplicate identity.

## 8. Boot identity and EEPROM generation journal

### 8.1 Identity roles

- `generation_counter64`: persistent monotonically increasing boot generation.
- `boot_id64`: current boot identity, defined as the successfully committed generation value.
- `boot_challenge64`: fresh handshake challenge; proves response freshness but is not boot identity.
- `epoch_token32`: HELLO_ACK correlation token; may collide and is never used as device_epoch_id.
- RawLog `device_epoch_id`: full boot_id64 value encoded using the exact type/representation accepted in RawLog v2. The serial tag is only a truncated correlation field.

### 8.2 EEPROM journal proposal

Use a 16-slot wear-levelled EEPROM journal. Each 16-byte slot contains: magic/version (2 B), generation_counter64 (8 B), CRC16 (2 B), reserved (2 B), commit marker (2 B). Write a new slot in this order: invalidate target marker, write payload, write CRC, read back and verify, then write commit marker last. A slot is valid only when marker, magic/version and CRC all validate. On boot, scan all slots and select the highest valid generation; increment it and commit to the next slot. Do not overwrite the last known-good slot before the new slot verifies.

- **First provisioned boot:** a factory-provisioned empty-state marker must be distinguishable from corruption. If explicitly provisioned blank state is found, write generation 1 and verify before entering IDLE.
- **Normal boot:** select highest valid committed generation and commit generation+1 before enabling session/ARM.
- **Power loss during write:** incomplete target slot is ignored; previous valid slot remains authoritative. On next boot, increment from the last valid generation.
- **Corrupt records:** ignore individual CRC-invalid slots only if at least one valid committed record remains. If all slots are invalid and the device is not in the explicit factory-empty state, identity is untrusted.
- **Write/readback failure, EEPROM unavailable, generation overflow, or ambiguous journal:** enter BOOT_ID_INVALID/FAULT, keep PWM disabled, reject ARM and all nonzero PWM commands, and do not create RawLog samples with a guessed epoch.
- No wrap is allowed for uint64 generation. At maximum value, fail closed.
- A factory reset/provisioning action is a separate controlled maintenance operation, not an automatic recovery from corruption.

This design requires a platform-specific EEPROM endurance and atomic-write review before implementation. It does not claim that EEPROM hardware behavior has been tested. A boot identity that cannot be durably established is a hard acquisition/session gate, not a random-ID fallback.

## 9. Unified state machine and transition table

### 9.1 States

`BOOT`, `BOOT_ID_INVALID`, `IDLE`, `ARMED`, `RUNNING`, `STOP_LATCHED`, `STOPPED`, `FAULT`, `FAULT_STOP`.

STOP is eligible in every state. `STOPPED` means software stop handling completed; it does not confirm physical zero current or motor standstill.

### 9.2 Transition rules

| Current state | Input/event | Acceptance rule | Next state | Output/action |
|---|---|---|---|---|
| BOOT | EEPROM identity valid and increment committed; protocol init valid | All initialization checks pass | IDLE | PWM remains 0; HELLO available |
| BOOT | identity invalid/corrupt/write failure | Any identity check fails | BOOT_ID_INVALID | PWM disabled; no ARM |
| BOOT_ID_INVALID | STOP | Always | FAULT_STOP | Request PWM=0; return STOP_ACK if transport works |
| BOOT_ID_INVALID | PWM_SET / ARM | Always reject | BOOT_ID_INVALID | ERROR; no PWM change |
| IDLE | ARM | Valid session, handshake, fresh token and no fault | ARMED | No drive; ARM_ACK/STATUS |
| IDLE | PWM_SET | Reject: not armed | IDLE | ERROR; PWM remains 0 |
| ARMED | PWM_SET(pwm=0..30) | Valid CRC/header/session/command/token; no stop latch | RUNNING if pwm>0, otherwise ARMED | Apply exact PWM; emit APPLY_ACK |
| ARMED | invalid PWM_SET | Any validation failure | ARMED or FAULT if internal invariant fails | ERROR; no nonzero output |
| RUNNING | PWM_SET(pwm=0..30) | Current session/token, fresh command, no stop latch | RUNNING if >0; ARMED if 0 | Apply and ACK |
| RUNNING | STOP | Always | STOP_LATCHED | Invalidate ARM; PWM=0; STOP_ACK |
| ARMED | STOP | Always | STOP_LATCHED | Invalidate ARM; PWM=0; STOP_ACK |
| IDLE | STOP | Always | STOP_LATCHED | PWM=0; STOP_ACK |
| STOP_LATCHED | STOP duplicate/new | Always | STOP_LATCHED | PWM=0; ACK history outcome |
| STOP_LATCHED | PWM_SET including zero | Reject as drive/session command; STOP remains latched | STOP_LATCHED | PWM=0; ERROR or idempotent status |
| STOP_LATCHED | ARM | Re-arm only after new host synchronization boundary and new session token | ARMED | No drive; clear latch only after accepted ARM |
| STOP_LATCHED | stop handling completion | PWM-zero request accepted by output adapter | STOPPED | Report software completion, not physical confirmation |
| STOPPED | STOP | Always | STOPPED | Idempotent ACK |
| STOPPED | PWM_SET | Reject until new ARM/session | STOPPED | ERROR; PWM=0 |
| STOPPED | new valid ARM | New synchronized session and valid boot identity | ARMED | No drive |
| Any non-stop state | protocol/internal fatal fault | Defined fatal condition | FAULT | Immediately request PWM=0 and invalidate ARM |
| FAULT | STOP | Always | FAULT_STOP | Retry PWM=0 request; STOP_ACK if possible |
| FAULT | ARM/PWM_SET | Reject | FAULT | ERROR; no drive |
| FAULT_STOP | STOP | Always | FAULT_STOP | Idempotent safe action |
| FAULT_STOP | ARM/PWM_SET | Reject | FAULT_STOP | No drive; recovery requires explicit maintenance/reinitialization |

STOP acceptance has priority over queued PWM_SET. The command dispatcher must check the stop latch immediately before applying any nonzero PWM, not only when the frame is first parsed. A PWM command received before STOP but still queued when STOP is latched must be discarded.

A failure to confirm PWM output state is not a transition to a claim of physical stop. It is a fault and requires external safety action under a separately approved hardware procedure.

## 10. ADC timestamps and clock rollover

For each conversion, capture `micros()` immediately before and after `analogRead()`; store their midpoint as `timestamp_us_u32` and set the semantic timestamp point to `conversion_midpoint`. This is an estimate around the conversion call, not the ADC sample-and-hold instant. On Uno, micros() granularity is 4 µs, not 1 µs.

The 32-bit microsecond timer wraps at approximately 71.6 minutes. Python unwraps using modular differences only within a validated boot_id64 epoch. A modular gap must be less than 2^31 µs (about 35.8 minutes) to distinguish forward progress unambiguously. The sample sequence is uint16 and wraps after 65,536 attempted conversions; use both sequence and timestamp and treat discontinuity as a possible loss/reset signal.

If the host begins receiving after a wrap and cannot reconstruct the boot-relative elapsed time, it must store a documented first-observed-relative origin or mark boot-relative elapsed time unavailable. It must not fabricate an absolute elapsed value. Device epoch association is invalid if boot_id64 is not verified.

## 11. Acquisition failure boundary

- Invalid channel code or invalid acquisition precondition is detectable.
- Conversion timeout is detectable only if a custom bounded ADC conversion routine is implemented and has a defined timeout. Standard Arduino `analogRead()` does not expose a per-conversion failure result.
- Sensor disconnection, floating input and electrically implausible values are not generally distinguishable from valid ADC codes by `analogRead()` alone. They are not automatically labeled conversion failures.
- `adc_raw=0xFFFF` is reserved for no valid conversion code; a valid raw code of 0 is preserved.
- Status 0 means a conversion code was acquired. Status 1/2/3 means no valid code for the stated reason. A2/A3 reference-channel status does not change control or measurement eligibility.

A future analog plausibility or sensor-open diagnostic must be specified and validated separately; it must not be smuggled into acquisition_status.

## 12. Loss, overflow and sequence semantics

### 12.1 Counters

Maintain a uint32 cumulative `loss_counter` per boot epoch, initialized to zero after successful boot identity establishment. It increments once for each sample attempt that cannot be delivered into an owned batch due to local acquisition-buffer exhaustion or a batch being discarded before transmission. It does not increment merely because a conversion status reports an acquisition failure; that attempt still has a sample record and sequence.

Maintain separate uint16 `sample_sequence` and uint16 `batch_sequence`, both incremented for each attempted sample/batch respectively, including attempts that later cannot be transmitted. Counters wrap modulo their width. STATUS reports the full uint32 loss_counter and last attempted sample sequence. ADC_BATCH carries the low 8 bits as a snapshot only.

### 12.2 Detectable versus undetectable loss

- A gap in sample_sequence within one verified boot epoch detects one or more missing attempted sample records, subject to sequence-wrap disambiguation.
- A gap in batch_sequence detects missing batches, subject to wrap disambiguation.
- A rising loss_counter identifies locally detected acquisition/buffer/queue loss. Python records the observed counter delta.
- A counter reset without a new verified boot_id64 is a protocol fault; do not assume a new epoch.
- A lost final batch with no later STATUS/sample may be undetectable until reconnect. The protocol cannot guarantee notification over a failed link.
- Sensor disconnection or an electrically invalid but in-range ADC value is not necessarily detectable as sample loss.
- UART corruption is detected by CRC, but a corrupted frame cannot reveal all fields; Python records a transport error and waits for subsequent sequence/counter evidence.

### 12.3 Buffer overflow behavior

Never overwrite a batch currently owned by TX. If no free acquisition batch slot exists, increment loss_counter for every sample attempt that cannot be retained and continue sequence numbering. STATUS reports the loss counter as soon as the TX path permits. Do not fabricate replacement samples or timestamps. No stage is silently declared complete because samples were lost.

### 12.4 Exact RawLog v2 field mapping (PR #180 / accepted schema)

The mapping below is constrained by `docs/RAWLOG_V2_INDEPENDENT_SCHEMA.md` at accepted 310-1 HEAD `5db3314ddf1efc2c068330ac333367662542ae5c`. It does not add fields to that schema.

| Serial / host source | RawLog v2 destination | Mapping rule |
|---|---|---|
| Python-generated sample identity | ADC_SAMPLE.record_id and sample_id | Generate one unique ID per ADC conversion; use the same ID where the schema example uses sample_id. |
| Python package writer order | Common record_seq | Assign monotonically in append order; never use device sample sequence as record_seq. |
| measurement_session_id | Common measurement_session_id | Preserve the host UUID/string unchanged. |
| Verified full boot_id64 from handshake | ADC_SAMPLE.device_epoch_id | Serialize as the accepted schema's string value, consistently for the whole boot epoch. The 32-bit header device_epoch_tag is correlation-only and MUST NOT be written as device_epoch_id. If the full boot_id64 is not received and verified, do not fabricate an epoch; acquisition/session association remains unresolved. |
| sample_sequence (uint16) | ADC_SAMPLE.device_sample_sequence | Store the observed unsigned integer 0–65535, preserving wrap semantics in transport evidence. The accepted schema describes this as a monotonically increasing sequence but does not explicitly define uint16 rollover; this is a schema-contract ambiguity requiring commander resolution before implementation. |
| channel_code | ADC_SAMPLE.channel | 0=A0, 1=A1, 2=A2, 3=A3, 4=A4, 5=A5. |
| Channel lookup | ADC_SAMPLE.sensor / signal_role | A0=ACS712 #1 / winding_current; A1=ACS712 #2 / brush_stability_observation; A2=magnetic_sensor / magnetic_reference; A3=thermistor / thermistor_reference; A4=voltage_input_v4 / voltage_v4; A5=voltage_input_v5 / voltage_v5. |
| adc_raw + acquisition_status | ADC_SAMPLE.adc_raw / validity / invalid_reason | Status 0: preserve 0–1023 raw integer, validity=valid, invalid_reason=null. Status 1/2/3: validity=unavailable, adc_raw=null, invalid_reason is the corresponding explicit status reason. Never persist 0xFFFF as a valid ADC code. |
| timestamp_us_u32 | ADC_SAMPLE.device_timestamp_us_u32 | Preserve the uint32 value for a successful conversion. For an unavailable conversion, follow the schema's null timestamp rule. |
| Timestamp semantics | ADC_SAMPLE.device_timestamp_point | Fixed value conversion_midpoint, as defined by the acquisition contract. |
| Python clock unwrapping | ADC_SAMPLE.device_elapsed_us | Store the unwrapped value only when unambiguous within the verified epoch; otherwise null. Never infer across an ambiguous wrap. |
| Python receive clocks | ADC_SAMPLE.host_received_at_utc / host_received_monotonic_ns | Capture per received sample/frame according to the host receive contract; do not substitute batch transmit time for device acquisition time. |
| stage_context_token + context map | ADC_SAMPLE.stage_context_id / stage_id / stage_assignment | Resolve token using measurement_session_id AND verified device_epoch_id. Write the mapped UUID and stage ID only on exact match; otherwise null IDs and unresolved. The uint16 token is not stored in the UUID field. |
| Calibration context | ADC_SAMPLE.calibration_id | Null unless an accepted CALIBRATION is scoped_for_application for this channel and sample interval. Current proposal does not establish such scope, so null is the default. |
| ADC resolution | ADC_SAMPLE.adc_resolution_bits | 10 for the specified Uno ADC; raw_unit=count. |
| Acquisition status | ADC_SAMPLE.validity / invalid_reason | No additional acquisition_status field is added to RawLog v2. Preserve the raw status byte in transport evidence if required for protocol forensics. |

**Fields that do not exist in the accepted ADC_SAMPLE schema:** `batch_sequence`, `loss_counter_snapshot`, full `loss_counter`, `stage_context_token`, `acquisition_status`, and `sample_flags`. Do not add them to ADC_SAMPLE or overload unrelated fields. Preserve these values in a separately versioned transport-evidence artifact/metadata path only after that path is defined and approved. Until then, sequence gaps and loss-counter observations can be reported in the design/test evidence but have no approved persistent RawLog v2 field mapping. This is an explicit integration gap, not a claim of completed RawLog mapping.

The proposed 32-bit `device_epoch_tag` in the common wire header is insufficient to populate the accepted full `device_epoch_id` by itself. The handshake must return the full committed boot_id64 and Python must verify it before associating samples. The HELLO/HELLO_ACK byte layout and full boot identity transfer are not yet specified in §6; this remains a protocol-definition blocker.

The accepted schema requires one ADC_SAMPLE per conversion. ADC_BATCH is only a transport envelope: Python must emit 12 independent ADC_SAMPLE records for the 12 conversion units in a complete batch. A2/A3 records, if included, remain reference observations and must not affect control, acceptance, eligibility or derived estimates.

## 13. RawLog v2 contract boundary

Issue #170 and the accepted RawLog v2 schema are authoritative for field names, types, nullability, envelope, record types and storage. This document defines serial-side source data and candidate mapping only; it does not redefine RawLog v2.

The exact mapping above is not fully closed: the accepted schema has no fields for batch-level sequencing/loss evidence or the raw stage token, and its device_sample_sequence rollover semantics need clarification. These gaps must be resolved by the 310-4 commander / schema authority before implementation. No schema field may be invented locally. The 32-bit device_epoch_tag cannot stand in for the full device_epoch_id.

Do not require legacy RawLog v1 columns or old derived values. Do not generate derived values on Arduino. Do not use A1 as winding current. Do not use A2/A3 for automatic control or eligibility. Do not fill missing data with zero or previous values.

## 14. TX scheduling, ownership and SRAM feasibility gate

### 14.1 Throughput

UART 57600 bps, 8N1 has a theoretical ceiling of 5,760 wire bytes/s. Using wire maxima:
- ADC_BATCH: 194 B × 10/s = 1,940 B/s.
- STATUS: 31 B × 1/s = 31 B/s (one status per second baseline; event-driven statuses add traffic).
- APPLY_ACK: 25 B × 31 stage transitions / 310 s = 2.5 B/s.
- Nominal subtotal = approximately 1,973.5 B/s, about 34.3% of theoretical UART capacity, before STOP/ERROR/handshake/event traffic.

This average is not a latency guarantee. Worst-case bursts and serial driver backpressure must be bounded.

### 14.2 Priority and ownership

Priority: (1) STOP_ACK and fault/error, (2) APPLY_ACK and session-critical STATUS, (3) ADC_BATCH, (4) noncritical diagnostics.

A frame is transmitted atomically with respect to other frames: bytes from different frames are never interleaved. TX owns the selected source buffer until the final delimiter has been accepted by UART. The scheduler may write only a bounded chunk no larger than the currently available UART TX capacity, then return to the main loop. STOP processing must not wait for a full ADC_BATCH transmission. A buffer cannot be reused while TX owns it.

The acquisition producer and TX consumer require an explicit ownership state per buffer (FREE → FILLING → READY → TX_OWNED → FREE). Ownership changes must be atomic with respect to the main loop/interrupt context. ISR code must not perform serial writes, CRC/COBS encoding, or unbounded copies. Shared multi-byte counters and ownership flags require atomic snapshot/update or a short bounded critical section. The main loop remains responsible for framing and transmission.

### 14.3 SRAM status

**SRAM fit is not established.** Uno SRAM is 2 KB. The design has not yet provided compiler-backed sizes for common header, RX frame, TX frame, batch buffers, four STOP history entries, UART rings, globals, heap and worst-case stack. A 194-byte wire frame does not mean only 194 bytes of memory are needed. Two full batch buffers plus independent RX/TX encoded buffers may be infeasible.

Before implementation, the design must choose a concrete memory layout and provide:
- sizeof/map output for every static buffer and structure;
- Arduino core/HardwareSerial ring allocation;
- stack high-water measurement or defensible bound under worst nested call path;
- proof that no dynamic String/heap allocation is used in the acquisition/STOP path;
- maximum buffer occupancy and scheduler latency under worst-case UART backlog;
- proof that STOP is serviced while TX is backpressured and while a batch is being assembled.

No claim of nonblocking operation or SRAM fit is made by this draft. If the memory budget fails, return to design review; do not silently reduce samples, drop records, or change RawLog semantics.

## 15. Python compatibility and command behavior

The accepted 310-3 interface currently includes `MessageCodec.encode_pwm(pwm:int)->bytes`, `encode_stop()->bytes`, and `decode(payload:bytes)->object`. The transport supports partial/multiple frames and ACKs. The current interface does not itself establish all session, command and stage-context correlation described here.

The required future additive contract is:
- PWM_SET contains command_id and stage_context_token.
- APPLY_ACK echoes command_id and stage_context_token.
- Python maintains the UUID context map before command transmission.
- ADC_BATCH carries the device-snapshotted token for every conversion.
- Python never assigns late telemetry to whichever stage happens to be active at receive time.
- Existing send_pwm(pwm) call sites and tests remain unchanged until a separately reviewed compatibility change is authorized.

This document does not authorize Python changes.

## 16. Acceptance evidence before implementation

A future submission must include:
1. Byte-exact protocol definitions and independently reproduced length arithmetic.
2. Test vectors for every message, CRC, COBS boundary, malformed frame and reserved enum.
3. Context-map examples across stage transition, delayed telemetry and reboot.
4. STOP history examples: first request, exact duplicate, ID conflict, stale session, full history.
5. EEPROM journal cases: first provision, normal boot, interrupted write, corrupt slots, readback failure and overflow.
6. Full state transition test matrix, including queued PWM_SET followed by STOP.
7. Loss-counter and sequence-gap examples, wrap behavior, and undetectable final-loss boundary.
8. Sampling adequacy analysis for threshold statistic, signal bandwidth, PWM frequency, analog filter, settling and aliasing.
9. Compiler-backed SRAM/stack map and backpressure test evidence.
10. RawLog mapping confirmation against the exact accepted Issue #170/PR #180 schema without adding fields.
11. Review disposition for all nine findings in this resubmission.

No physical hardware activity is authorized by this document.

## 17. Review correction matrix

| # | Review finding | v0.5 re-submission response |
|---:|---|---|
| 1 | ADC_BATCH length and traffic mismatch | §4.2, §6.3: decoded 192 B, COBS 193 B, wire 194 B; 1,940 wire B/s |
| 2 | stage_context_id/token mapping undefined | §5: UUID↔uint16 map, session/epoch namespace, pre-command persistence, unresolved behavior |
| 3 | No actual state transition table | §9: explicit state/event/acceptance/next-state/action table |
| 4 | STOP_ACK length unsupported | §6.2, §7.2: three payload bytes, enum codes and 22/23/24 B lengths |
| 5 | Syntax/edit corruption | Full document rewritten and syntax pass required; malformed punctuation examples corrected |
| 6 | Boot identity persistence conditional | §8: 16-slot EEPROM journal, CRC, commit marker, failure/first boot/overflow fail-closed |
| 7 | Loss/overflow undefined | §12: counters, increments, resets, sequence mapping, detection limits and RawLog boundary |
| 8 | 20 Hz adequacy unsupported | §4.3–4.4: candidate only; Nyquist/bandwidth/aliasing limitations and required evidence |
| 9 | SRAM/TX implementation unproven | §14: ownership model and exact evidence gate; explicitly not claimed feasible |

## 18. Submission decision requested

Review this integrated document as a draft design proposal. The exact RawLog field mapping remains subordinate to the accepted Issue #170/PR #180 schema; the sampling cadence and SRAM feasibility remain open gates. This document does not assert that those gates have passed. Do not merge, implement, compile, upload, connect serial hardware, energize the motor, perform the 310-second measurement, or advance to 310-5 based solely on this submission.
