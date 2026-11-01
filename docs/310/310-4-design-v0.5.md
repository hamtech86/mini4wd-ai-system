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

| Message | Payload definition | Payload | Decoded | COBS max | Delimiter | Wire max |
|---|---|---:|---:|---:|---:|---:|
| HELLO | host_nonce64 | 8 B | 27 B | 28 B | 1 B | 29 B |
| HELLO_ACK | result u8 + boot_id64 u64 + echoed host_nonce64 | 17 B | 36 B | 37 B | 1 B | 38 B |
| ARM | stage_context_token u16 + initial_pwm u8 (MUST be 0) | 3 B | 22 B | 23 B | 1 B | 24 B |
| ARM_ACK | result u8 + state u8 + active_context_token u16 | 4 B | 23 B | 24 B | 1 B | 25 B |
| PWM_SET | pwm u8 + stage_context_token u16 | 3 B | 22 B | 23 B | 1 B | 24 B |
| APPLY_ACK | result u8 + applied_pwm u8 + stage_context_token u16 | 4 B | 23 B | 24 B | 1 B | 25 B |
| STOP_REQ | stop_reason u8 + stop_request_id u16 | 3 B | 22 B | 23 B | 1 B | 24 B |
| STOP_ACK | requester_relation u8 + request_outcome u8 + latched_state u8 | 3 B | 22 B | 23 B | 1 B | 24 B |
| STATUS | state u8 + active_pwm u8 + active_context_token u16 + loss_counter u32 + last_sample_sequence u16 | 10 B | 29 B | 30 B | 1 B | 31 B |
| ERROR | error_code u8 + offending_message_type u8 + detail_code u16 + related_command_id u32 | 8 B | 27 B | 28 B | 1 B | 29 B |
| ADC_BATCH | payload defined in §4.2 | 173 B | 192 B | 193 B | 1 B | 194 B |

All values are proposed v1 definitions, not accepted production wire compatibility. boot_id64 is uint64 little-endian. host_nonce64 is a host-generated fresh 64-bit challenge unique to each HELLO attempt; it is not a persistent identity. HELLO carries a nonzero measurement_session_tag and device_epoch_tag=0. HELLO_ACK echoes the session tag and carries the nonzero device epoch correlation tag derived from boot_id64. The payload echoes host_nonce64 exactly.

### 6.2.1 Message type codes and common header validation

Candidate v1 message_type codes: HELLO=0x01, HELLO_ACK=0x02, ARM=0x03, ARM_ACK=0x04, PWM_SET=0x10, APPLY_ACK=0x11, STOP_REQ=0x20, STOP_ACK=0x21, STATUS=0x30, ERROR=0x31, ADC_BATCH=0x40. Other codes are rejected without output change. Header flags MUST be zero. magic and protocol_version require exact match. command_id=0 is reserved for HELLO/HELLO_ACK and unsolicited STATUS/ADC_BATCH/ERROR; command-bearing requests and ACKs require nonzero command_id.

device_epoch_tag is the low 32 bits of verified boot_id64; if that value is zero, use 0xFFFFFFFF only as the header correlation tag. The full boot_id64 remains the identity. measurement_session_tag is a nonzero host correlation tag allocated for one measurement_session_id and not reused within a host process. These tags are not security credentials and never replace full identifiers in RawLog or evidence.

For non-STOP requests, validation order is: (1) frame boundary/COBS, (2) minimum and exact length, (3) CRC, (4) magic/version/flags/type/reserved enums, (5) verified boot epoch tag, (6) active session tag, (7) command_id freshness and duplicate consistency, (8) state and context-token eligibility, (9) action. No PWM or ARM change occurs before all checks pass. STOP_REQ is the safety exception: after valid frame/length/CRC/basic syntax, act even if session or epoch tags are stale; ACK reports the relation. A malformed or CRC-invalid STOP is not trusted and is not acted upon.

### 6.2.1.1 Wire enum registry

HELLO_ACK result: 0=OK, 1=BOOT_ID_INVALID, 2=PROTOCOL_UNSUPPORTED, 3=SESSION_BUSY, 4=INVALID_CHALLENGE. A nonzero result never authorizes ARM; boot_id64 is zero when no valid committed identity exists, and the host must reject it.

ARM_ACK result values are defined in §6.2.3. ARM_ACK state and STATUS state use the same codes: 0=IDLE, 1=ARMED, 2=RUNNING, 3=STOP_LATCHED, 4=STOPPED, 5=FAULT, 6=FAULT_STOP, 7=BOOT_ID_INVALID. BOOT is initialization-only and is never reported as an ARM-success state. Unknown state codes are invalid.

APPLY_ACK result: 0=APPLIED, 1=REJECTED_STATE, 2=INVALID_SESSION, 3=INVALID_EPOCH, 4=INVALID_COMMAND, 5=INVALID_CONTEXT, 6=PWM_OUT_OF_RANGE, 7=STOP_LATCHED, 8=OUTPUT_FAULT. applied_pwm echoes the actual accepted software output value; on nonzero result it MUST be zero and no nonzero PWM is applied. PWM_SET pwm is restricted to integer 0..30 inclusive.

ERROR error_code: 1=BAD_FRAME, 2=BAD_CRC, 3=BAD_VERSION, 4=UNKNOWN_MESSAGE, 5=INVALID_ENUM, 6=STALE_SESSION, 7=STALE_EPOCH, 8=ID_CONFLICT, 9=COMMAND_REGRESSION, 10=NOT_ARMED, 11=INVALID_CONTEXT, 12=BOOT_ID_INVALID, 13=FAULT_ACTIVE, 14=INTERNAL_INVARIANT. detail_code is message-specific and MUST be zero when no detail is defined. All unassigned values are reserved and rejected.

### 6.2.2 HELLO / HELLO_ACK handshake

Handshake is required after every device boot and before ARM. Host creates a new measurement_session_id and nonzero session tag, then sends HELLO with fresh host_nonce64 and command_id=0.

1. Device accepts HELLO only after EEPROM boot identity has been committed and protocol initialization is valid. BOOT_ID_INVALID/FAULT never fabricates an identity.
2. Device validates protocol version, flags, CRC and nonce field; it binds the requested session tag to current boot_id64 and records the nonce as the active challenge.
3. HELLO_ACK returns result=0 (OK), full committed boot_id64 and exact echoed host_nonce64. Header echoes measurement_session_tag and carries the epoch tag derived from boot_id64.
4. Host accepts only if nonce and session tag exactly match the outstanding HELLO, result is OK, boot_id64 is nonzero, and epoch tag matches its derivation. Host then binds full boot_id64 to measurement_session_id.
5. Retry with same session tag and nonce is idempotent. Same session tag with a different nonce replaces the pending challenge only when not ARMED/RUNNING; otherwise reject. A different session tag invalidates prior ARM permission and command sequencing before binding the new session.
6. Reboot increments and commits boot_id64 before any handshake. Delayed HELLO_ACK is rejected unless nonce matches the current outstanding request.

No sample is associated with a session until full boot_id64 is verified. The 32-bit epoch tag is only a correlation check.

### 6.2.3 ARM / ARM_ACK handshake

ARM is an explicit permission step after HELLO; HELLO alone never enables PWM. ARM uses a fresh nonzero command_id, active session tag and verified epoch tag. Payload contains first stage_context_token and initial_pwm=0. Device accepts only with valid boot identity, current HELLO binding, exact session/epoch match, nonzero token, no fatal fault, and state IDLE, STOP_LATCHED or STOPPED. ARM_ACK echoes command_id and returns result, resulting state and active token.

ARM result codes: 0=ARMED, 1=REJECTED_STATE, 2=INVALID_SESSION, 3=INVALID_EPOCH, 4=INVALID_CONTEXT, 5=BOOT_ID_INVALID, 6=FAULT_ACTIVE. Success requires result=0, state=ARMED and echoed token match. ARM never applies nonzero PWM. First PWM_SET is a separate command with a new command_id.

Exact duplicate command_id plus byte-identical payload returns cached identical ARM_ACK without repeating the transition. Same command_id with different payload returns ERROR(ID_CONFLICT), never arms. A new ARM command_id while already armed is rejected except for the STOP recovery procedure in §9.3. Host timeout never implies ARM success; retry exact frame or restart HELLO with a new session tag.

### 6.2.4 Retry, duplicate and command freshness

For ARM/PWM_SET, device retains a bounded recent-command cache for active session. Exact duplicate command_id and identical request bytes returns original ACK without reapplying output. Reuse of command_id with different bytes is ID_CONFLICT. New command_ids must be strictly increasing; gaps are allowed, regressions rejected. Cache retains at least four recent outcomes; monotonic high-water mark prevents an evicted old ID being treated as new. Host retries only byte-identical frames with same command_id. STOP_REQ uses separate stop_request_id history in §7 and is always treated as a safety request.

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

Use a 16-slot wear-levelled EEPROM journal occupying 256 bytes. Each 16-byte slot contains: magic/version (2 B), generation_counter64 (8 B), reserved (3 B, all zero), CRC16 (2 B), commit marker (1 B; invalid=0x00, committed=0xA5). CRC-16/CCITT-FALSE is computed over bytes 0–12, init=0xFFFF, poly=0x1021, xorout=0x0000; CRC is stored at bytes 13–14 and marker at byte 15. A slot is valid only when marker equals the exact committed value, magic/version match and CRC validates.

**Write order and interrupted-write reasoning**
1. Select the next ring slot; never target the current highest valid slot.
2. Write target marker to invalid value and read it back. Do not touch payload unless invalidation is verified.
3. Write magic/version, generation and reserved bytes, then CRC; read back complete payload and independently recompute CRC.
4. Write the one-byte committed marker last and read it back. Only after successful readback is the new generation committed.
5. On boot, scan all slots and select highest valid generation. A power cut during payload writing leaves marker invalid. A power cut during final marker programming leaves it invalid or valid; if valid, the payload and CRC had already been fully written and verified. The prior committed slot is never overwritten in this operation.

Factory-empty state is not inferred from blank journal bytes alone. Reserve EEPROM addresses 256–259 for a separate one-time provisioning record: magic bytes 0x50,0x52, version 0x01, and CRC-8/ATM over the first three bytes (poly=0x07, init=0x00, xorout=0x00). This record is written and read back during controlled factory provisioning, before first boot. If all journal slots are invalid, generation 1 may be created only when this provisioning record validates AND all 256 journal bytes are erased (0xFF). Any other all-invalid condition is corruption and enters BOOT_ID_INVALID. The provisioning record is never automatically recreated or repaired by firmware.

- **First provisioned boot:** valid provisioning record plus fully erased journal permits generation 1; commit and verify before IDLE.
- **Normal boot:** select highest valid committed generation and commit generation+1 before enabling session/ARM.
- **Power loss during write:** incomplete target slot is ignored; previous valid slot remains authoritative. Next boot increments from the last valid generation.
- **Corrupt records:** ignore individual invalid slots only if at least one valid committed record remains. If no valid slot remains and explicit factory-empty predicate is false, identity is untrusted.
- **Write/readback failure, EEPROM unavailable, generation overflow or ambiguous journal:** enter BOOT_ID_INVALID/FAULT, keep PWM disabled, reject ARM and nonzero PWM commands; never guess an epoch.
- No uint64 generation wrap. At maximum value, fail closed.
- Factory reset/provisioning is a separate controlled maintenance operation, not automatic recovery from corruption.

**Endurance estimate (conditional, not a guarantee):** ATmega328P EEPROM endurance is specified as 100,000 write/erase cycles per cell under datasheet test conditions. Each slot is selected once per 16 successful boots. The marker cell receives at most two writes per slot use (invalidate + commit), giving a simplified marker-limited estimate of 100,000 × 16 / 2 = 800,000 boots. Payload cells receive at most one write per slot use, giving approximately 1,600,000 boots. Illustrative marker-limited life: 1 boot/day ≈ 2,192 years; 10 boots/day ≈ 219 years; 100 boots/day ≈ 21.9 years. These projections exclude temperature/voltage derating, abnormal retries, manufacturing variation, write amplification and other EEPROM uses; they are arithmetic projections, not service-life promises. Expected project boot frequency is not specified, so acceptance requires a lifetime target and worst-case write-count budget.

The one-byte commit marker avoids a multi-byte marker torn-write ambiguity. This still depends on valid supply voltage during EEPROM programming; brownout behavior and reset thresholds require review. CRC detects payload corruption but does not alone guarantee power-fail behavior. This journal is a proposal, not a tested persistence guarantee. A boot identity that cannot be durably established is a hard session gate, not a random-ID fallback.

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
| IDLE | HELLO | Valid committed boot identity, valid nonce and nonzero session tag | IDLE | Bind session; HELLO_ACK; no ARM |
| STOP_LATCHED / STOPPED | HELLO | Valid committed boot identity, new session tag and fresh nonce | same state | Bind new session; HELLO_ACK; retain STOP latch |
| IDLE / STOP_LATCHED / STOPPED | ARM | Verified HELLO session+epoch, fresh command_id, nonzero context token, initial_pwm=0, no fatal fault | ARMED | ARM_ACK; PWM remains 0 |
| IDLE | PWM_SET | Reject: not armed | IDLE | ERROR; PWM remains 0 |
| ARMED | PWM_SET(pwm=0..30) | Valid CRC/header/session/command/token; no stop latch | RUNNING if pwm>0, otherwise ARMED | Apply exact PWM; emit APPLY_ACK |
| ARMED | invalid PWM_SET | Any validation failure | ARMED or FAULT if internal invariant fails | ERROR; no nonzero output |
| RUNNING | PWM_SET(pwm=0..30) | Current session/token, fresh command, no stop latch | RUNNING if >0; ARMED if 0 | Apply and ACK |
| RUNNING | STOP | Always | STOP_LATCHED | Invalidate ARM; PWM=0; STOP_ACK |
| ARMED | STOP | Always | STOP_LATCHED | Invalidate ARM; PWM=0; STOP_ACK |
| IDLE | STOP | Always | STOP_LATCHED | PWM=0; STOP_ACK |
| STOP_LATCHED | STOP duplicate/new | Always | STOP_LATCHED | PWM=0; ACK history outcome |
| STOP_LATCHED | PWM_SET including zero | Reject as drive/session command; STOP remains latched | STOP_LATCHED | PWM=0; ERROR or idempotent status |
| STOP_LATCHED | stop handling completion | PWM-zero request accepted by output adapter | STOPPED | Report software completion, not physical confirmation |
| STOPPED | STOP | Always | STOPPED | Idempotent ACK |
| STOPPED | PWM_SET | Reject until new ARM/session | STOPPED | ERROR; PWM=0 |

| Any non-stop state | protocol/internal fatal fault | Defined fatal condition | FAULT | Immediately request PWM=0 and invalidate ARM |
| FAULT | STOP | Always | FAULT_STOP | Retry PWM=0 request; STOP_ACK if possible |
| FAULT | ARM/PWM_SET | Reject | FAULT | ERROR; no drive |
| FAULT_STOP | STOP | Always | FAULT_STOP | Idempotent safe action |
| FAULT_STOP | ARM/PWM_SET | Reject | FAULT_STOP | No drive; recovery requires explicit maintenance/reinitialization |

STOP acceptance has priority over queued PWM_SET. The command dispatcher must check the stop latch immediately before applying any nonzero PWM, not only when the frame is first parsed. A PWM command received before STOP but still queued when STOP is latched must be discarded.

A failure to confirm PWM output state is not a transition to a claim of physical stop. It is a fault and requires external safety action under a separately approved hardware procedure.

### 9.3 STOP後の再ARMと遅延フレーム排除

STOP後の再ARMは同一セッションを継続して行わない。次の条件を順番どおり満たす場合だけ許可する。

1. STOPをラッチした時点でARM許可を無効化し、未処理PWM_SETキューを破棄する。受信途中フレームもSTOP処理後は旧コマンドとして扱う。
2. ホストが再開を明示決定し、新しいmeasurement_session_idと、以前と異なるnonzero measurement_session_tagを割り当てる。旧セッションのcommand_idカウンタ/tokenを引き継がない。
3. ホストは新host_nonce64を含むHELLOを送る。デバイスは現在のboot_id64を維持したまま新セッションタグとnonceを検証してバインドする。HELLOはSTOP_LATCHED/STOPPED状態を解除しない。
4. HELLO_ACKのnonce、session tag、完全なboot_id64、epoch tagをホストが検証する。不一致なら中止する。
5. ホストは新セッション用token mapを永続化し、初回tokenを含むARM(initial_pwm=0)を新command_idで送る。
6. デバイスはCRC/構文→boot epoch→session tag→command_id→状態/トークンの順に検証する。STOPラッチはARMが全検証を通過した最後の時点でのみ解除する。ARM_ACK成功を受信・検証するまでPWM_SETを送らない。
7. 旧session tag、旧boot epoch tag、旧command_idのPWM_SET/ARMは常に拒否する。STOPだけは安全優先の例外として旧セッションからでもSTOP動作を試みる。

ホストは同一boot epoch内でsession tagを再利用しない。ホスト再起動後も再利用を防ぐ永続割当て方式はPython側設計審査で別途確定するまで未解決。デバイスは現在のsession tagとboot epoch tagが一致しない駆動コマンドを適用しない。

STOPとPWM_SETが同時に処理待ちの場合、STOPを先に処理しPWM_SETを破棄する。STOP後に受信バッファへ遅れて到着した旧フレームも、session/epoch不一致またはARM無効により出力へ到達しない。新HELLO/ARMは、旧セッション由来の受信フレームとコマンドキューを破棄した後にのみ処理する。

この手順はソフトウェア上の遅延フレーム排除要件であり、ハードウェア独立遮断や物理停止の証明ではない。

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

The proposed 32-bit `device_epoch_tag` in the common wire header is insufficient to populate the accepted full `device_epoch_id` by itself. The handshake must return the full committed boot_id64 and Python must verify it before associating samples. The HELLO/HELLO_ACK byte layout and full boot identity transfer are now proposed in §6.2; the byte protocol remains a candidate requiring independent test vectors and review, not accepted production compatibility.

### 12.5 Companion transport-evidence artifact (separate from RawLog v2)

To preserve protocol data with no accepted RawLog v2 field, propose one append-only UTF-8 JSONL companion file per measurement session, named transport-evidence-v1.jsonl, stored beside (not inside or merged into) the RawLog v2 stream. This is a separate artifact contract and does not modify RawLog v2. It must be included in the session package and reviewed before implementation.

Each line is one event and contains artifact_version="transport-evidence-v1", event_id (unique UUID), event_type, measurement_session_id, device_epoch_id (full boot_id64 string only when verified, otherwise null), host_received_at_utc, host_received_monotonic_ns, and direction. Event-specific fields:

- adc_batch_received: batch_sequence, sample_sequence_first, sample_sequence_last, sample_count, loss_counter_snapshot, raw_frame_base64, crc_valid.
- status_received: full uint32 loss_counter, last_sample_sequence, raw_frame_base64, crc_valid.
- sample_context_map: stage_context_token, stage_context_id UUID, stage_id, command_id, intended PWM, context-map creation timestamp and mapping result.
- transport_gap: expected/observed sample and batch sequence values, observed loss-counter delta, detection source, and whether the gap is conclusive or ambiguous.
- protocol_error: message type, error category, frame length, CRC result and raw frame bytes when safely available.

raw_frame_base64 contains the exact received COBS frame and delimiter. The companion artifact is append-only; corrections are new events referencing prior event_id, never in-place edits. A missing final frame cannot be reconstructed; the artifact records observed evidence only. Python must flush after each complete received frame and before orderly session finalization; crash durability/fsync policy requires Python-side approval. Never put the serial uint16 token in RawLog's UUID field. Never invent RawLog fields for companion data.

The companion file requires an explicit package manifest/hash and retention policy in the RawLog/session packaging design. Until that package-level contract is accepted, this persistence destination is proposed, not approved. If the companion artifact cannot be written, the session is evidence-incomplete and must not be represented as a complete loss-auditable measurement.

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
1. Byte-exact definitions and independently reproduced length arithmetic for HELLO, HELLO_ACK, ARM, ARM_ACK and all existing messages.
2. Test vectors for every message, CRC, COBS boundary, malformed frame, nonce mismatch, stale session/epoch, duplicate and reserved enum.
3. Context-map examples across stage transition, delayed telemetry and reboot.
4. STOP history examples: first request, exact duplicate, ID conflict, stale session, full history.
5. EEPROM journal cases: first provision, normal boot, interrupted write at every boundary, corrupt slots, readback failure and overflow; datasheet endurance and project boot-frequency budget.
6. Full state transition matrix, including old-session frames, delayed HELLO_ACK, queued PWM_SET followed by STOP and STOP→new HELLO→ARM.
7. Loss-counter/sequence-gap examples, wrap behavior, companion artifact persistence and undetectable final-loss boundary.
8. Sampling adequacy analysis for threshold statistic, signal bandwidth, PWM frequency, analog filter, settling and aliasing.
9. Compiler-backed SRAM/stack map and backpressure test evidence.
10. RawLog mapping confirmation against accepted Issue #170/PR #180 schema without additions; separate companion artifact package/hash/retention acceptance.
11. Review disposition for all prior findings and the four findings in the current review.

No physical hardware activity is authorized by this document.

## 17. Review correction matrix

| Review finding | Response in this integrated revision |
|---|---|
| Previous 9 findings | Retained in §§4–14: ADC_BATCH arithmetic, context mapping, state table, STOP_ACK, document integrity, boot journal, loss semantics, cadence limitations and SRAM/TX gate |
| Current #1: HELLO/HELLO_ACK/ARM/ARM_ACK undefined | §6.2–6.2.4: message type codes, exact payloads/lengths, nonce echo, full boot_id64 transfer, ARM rules, CRC/header validation order, retries and duplicates |
| Current #2: RawLog mapping incomplete | §12.4 exact mapping and explicit schema ambiguities; §12.5 separate append-only companion JSONL proposal for transport-only fields; no RawLog schema additions |
| Current #3: EEPROM endurance/power loss | §8.2: 16×16B journal, separate factory provisioning marker, one-byte commit marker, interrupted-write reasoning, conditional 100,000-cycle estimate and boot-frequency scenarios |
| Current #4: STOP→re-ARM stale-frame risk | §9.3: new session/nonce/token map, HELLO verification, fresh ARM, strict validation order, old session/epoch/command rejection and queue flush |

## 18. Submission decision requested

Review this integrated document as a draft design proposal. The companion transport-evidence artifact and package/retention contract, host-side persistent session-tag allocation, RawLog device_sample_sequence rollover semantics, EEPROM lifetime target, sampling cadence and SRAM feasibility remain open approval gates. The proposed message definitions are not accepted production wire compatibility. This document does not assert that any open gate has passed. Do not merge, implement, compile, upload, connect serial hardware, energize the motor, perform the 310-second measurement, or advance to 310-5 based solely on this submission.
