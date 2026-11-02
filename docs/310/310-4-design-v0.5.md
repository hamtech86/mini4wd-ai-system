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
- The schedule repeats every 100 ms. For each channel, consecutive sample intervals alternate **25 ms and 75 ms** (T→T+25 ms→T+100 ms→T+125 ms ...). The long-run average is 2 samples per 100 ms = 20 conversions/s/channel, but this is **non-uniform sampling**, not an equally spaced 20 Hz sample clock. One 12-sample batch is emitted per 100 ms, i.e. 10 batches/s.

This is a **candidate schedule, not an accepted sampling frequency or requirement**. The sample order within each scan is A0, A1, A4, A5, A2, A3. The time of each conversion is its own timestamp; channel order does not imply simultaneous sampling.

### 4.4 Cadence adequacy boundary

The alternating 25/75 ms intervals have a long-run average rate of 20 conversions/s/channel, but there is no single uniform sampling interval and the ordinary uniform-sampling Nyquist=10 Hz argument does not apply directly. The periodic timing pattern can introduce phase-dependent aliasing and spectral artifacts; it cannot be treated as an equally spaced 20 Hz record or used for a simple 10 Hz Nyquist claim. It cannot resolve PWM-frequency ripple or fast commutation transients. ACS712 bandwidth and motor/PWM dynamics can be far above this average event rate.

For the stated threshold/resistance purpose, 20 Hz may be adequate only for a deliberately defined low-frequency statistic (for example, a stable-window mean/dispersion computed in Python) after settling and aliasing are evaluated. It is not sufficient evidence for peak/ripple/current-transient characterization. The analog front-end filter, PWM frequency, expected signal bandwidth, channel-switch settling time, threshold decision statistic, required uncertainty, and acceptable timing jitter have not yet been specified. Therefore the 25/75 ms schedule remains a transport/acquisition candidate only; neither '20 Hz sampling' nor its adequacy may be claimed until those inputs and a non-uniform-sampling/aliasing analysis are reviewed. No firmware sampling-rate change is authorized here.

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

**Endurance arithmetic (conditional; not a device-life guarantee):** the ATmega328P data-sheet endurance figure is 100,000 write/erase cycles **per EEPROM cell**, subject to the specified voltage/temperature/test conditions. It is not 800,000 cycles per cell. With 16 journal slots and round-robin use, each slot is selected once per 16 committed boot events. At most two marker-cell write operations occur per selected slot use (invalidate marker, then commit marker); therefore a given marker cell sees at most 2 × (36,600 / 16) = 4,575 marker writes for the 36,600-event budget (rounding the per-slot distribution upward where needed). A payload cell written once per selected slot use sees at most ceil(36,600 / 16) = 2,288 writes. These are **per-cell** counts. Summed across all 16 marker cells, the journal performs at most 73,200 marker write operations over 36,600 boots; this aggregate is not a per-cell endurance rating. The idealized marker-cell lifetime arithmetic is 100,000 × 16 / 2 = 800,000 boot events, but this is a system-level rotation estimate derived from a per-cell limit, not '800,000 marker-cell cycles'. It excludes voltage/temperature derating, interrupted/retried writes, other EEPROM users, device variation and implementation defects. No service-life guarantee is claimed.

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
| RUNNING | STOP | Always | STOP_LATCHED | Invalidate ARM; PWM=0; STOP_ACK || ARMED | STOP | Always | STOP_LATCHED | Invalidate ARM; PWM=0; STOP_ACK |
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
| sample_sequence (uint16) | ADC_SAMPLE.device_sample_sequence | Host extends the wire uint16 to an epoch-scoped monotonic uint64 JSON integer in the existing integer field. Preserve the original uint16 and wrap evidence in transport-evidence-v1. No RawLog schema/type change. |
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

The exact mapping above is not fully closed: the accepted schema has no fields for batch-level sequencing/loss evidence or the raw stage token, and its device_sample_sequence rollover semantics need clarification. These gaps are resolved at the field-mapping level without modifying the accepted schema: (1) `device_sample_sequence` is already an integer and monotonically increasing within epoch; host-side uint64 expansion satisfies that existing semantic and type; (2) `batch_sequence`, `loss_counter`, raw `stage_context_token`, and raw uint16 sequence remain companion-artifact fields, never RawLog fields; (3) `transport-evidence-v1.jsonl` is a sibling package artifact listed in the package-level artifact inventory/manifest with byte length, SHA-256, schema/version and completeness state. It is not merged into `records.jsonl`. Issue #35 §3.4 expressly allows the detailed design to define concrete package representation; Issue #170/PR #180 continues to govern the RawLog schema. This closes the proposed design mapping without claiming that the companion manifest extension or its validator is already implemented/accepted. If the currently implemented manifest validator rejects companion artifacts, a separately reviewed package-manifest extension is required before implementation; do not alter RawLog v2 records or silently omit Evidence. The 32-bit device_epoch_tag cannot stand in for the full device_epoch_id.

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

---

# 310-4 v0.5 — Sixth-finding closure addendum (design proposal; supersedes conflicting open statements above)

This addendum responds to the six findings in the 2026-11-02 command review. It is part of the same design document and does not authorize implementation. Where this addendum supplies a concrete candidate, it remains subject to commander approval. No RawLog v2 schema change is proposed.

## A1. Host session-tag allocation across process restart

The earlier statement that a 32-bit `measurement_session_tag` is unique only within one host process is withdrawn. The candidate contract is a durable, never-reuse allocator:

1. The host maintains an append-only allocator journal keyed by a stable installation namespace. Each allocation transaction reserves the next uint32 value in the range 1..0xFFFFFFFE, commits it durably, and only then may HELLO be transmitted. Value 0 and 0xFFFFFFFF are reserved.
2. The tag is never returned to the free pool, including after a failed or abandoned session. Process restart, application upgrade and normal OS restart continue from the committed high-water mark. The full `measurement_session_id` UUID remains the authoritative identity; the 32-bit tag is only a wire correlation value.
3. Allocation must use an exclusive lock and atomic durable commit (write-ahead record, fsync, atomic checkpoint/rename, parent-directory fsync). A torn or corrupt journal, missing namespace, unavailable durable storage, or uncertain commit result causes fail-closed behavior: no HELLO, ARM or PWM_SET.
4. Backup/restore and host migration must preserve the allocator journal and namespace. A host that cannot prove continuity must not reset the counter or reuse a prior namespace. Recovery requires an explicitly provisioned new namespace plus a documented quarantine of the old host's outstanding sessions; until that recovery is approved, operation is blocked.
5. **32-bit collision policy:** there is no probabilistic collision resolution. A value already present in the journal is never issued again. Exhaustion at 0xFFFFFFFE is a hard stop requiring a separately reviewed protocol revision; wraparound is forbidden. The device rejects a HELLO whose tag equals a tag already bound to a different live session in the same boot epoch. It does not silently rebind it.
6. Delayed frames from an earlier session cannot match a newly allocated tag because tags are never reused. The full boot_id64 and host-side session UUID remain part of evidence correlation. Tags are not authentication or cryptographic anti-replay credentials.

This closes the design choice only if the host allocator journal is implemented with the durability properties above. It is not evidence that the current Python implementation already provides them.

## A2. Monotonic RawLog device_sample_sequence without changing RawLog v2

The wire `sample_sequence` remains uint16 and increments per attempted conversion continuously across all measurement sessions within one verified device boot epoch. It MUST NOT reset on HELLO, ARM, STOP recovery or session change. Only a new committed boot_id64 starts a new device sequence epoch.

The accepted RawLog v2 schema defines `device_sample_sequence` as an integer sequence that is monotonically increasing within a device epoch; it does **not** constrain the integer to uint16 or define a fixed bit width. The field is nullable when firmware does not provide it. Accordingly, the wire uint16 is not copied directly into this field. The host converts it into a monotonically extended unsigned 64-bit integer representation (serialized as a JSON integer) for `device_sample_sequence`, preserving the schema's existing integer type and monotonic meaning; no field, type, or schema version is changed. This is a semantic-preserving population of the existing field, not an amendment to the RawLog schema. The original wire uint16 remains separately retained in transport evidence.

- Maintain per-full-`device_epoch_id` state: last accepted uint16 value, extended uint64 value, last device timestamp, and continuity status.
- For each new sample, calculate modular delta = (new_u16 - last_u16) mod 65536. A forward delta in 1..32767 is eligible to advance the extended counter by that delta. Delta 0 is a duplicate candidate and must be deduplicated using exact frame/sample evidence; it is not assigned a new RawLog sequence. Delta 32768..65535 is ambiguous/backward and must not be guessed.
- A missing-sample gap may produce delta >1; the extended value advances by the observed modular delta and the gap is recorded in transport evidence. The host does not synthesize missing ADC_SAMPLE records.
- A wrap such as 65534, 65535, 0, 1 becomes extended values N, N+1, N+2, N+3. The resulting extended integer is stored in the existing RawLog v2 `device_sample_sequence` field; no schema field or type is added.
- The original uint16 value, batch_sequence, loss counters and wrap/continuity observations are retained in transport-evidence-v1, not added to RawLog.
- If no unambiguous forward relation can be established (e.g. host outage longer than the sequence ambiguity bound, unexplained device reset without a new verified epoch, or conflicting duplicate), the affected sample is not assigned a fabricated monotonic value. It is retained as unresolved transport evidence and the measurement package is marked sequence-incomplete pending review.

At 120 attempted conversions/s, uint16 wraps after 546.13 seconds. The 310-second single run produces at most 37,200 attempts and therefore does not itself wrap, but continuous counting is required for multiple sessions within one boot epoch. The host MUST NOT reset its extended base at a session boundary.

## A3. transport-evidence-v1 complete event and durability contract (companion-artifact proposal)

The companion JSONL file is the authoritative forensic record for protocol-level facts absent from RawLog v2. It remains a separate file and is not merged into RawLog records. This follows Issue #35 §3.4's direction that v2 is independent and that concrete storage representation/record splitting be defined in the detailed design; Issue #170 / the accepted PR #180 schema remains authoritative for RawLog records themselves. The companion file is a package-level sibling artifact, not an additional RawLog record type or a change to `records.jsonl`.

### A3.1 Required event coverage

Every protocol frame in either direction is recorded, including exact bytes and host timing:

- `frame_tx_intent`: event persisted before the first serial write; direction=host_to_device; message type, session/epoch tags, command_id, stop_request_id if applicable, exact COBS frame including delimiter as base64, frame length, allocated session UUID, and intended action.
- `frame_tx_complete`: after all frame bytes have been accepted by the host serial API; records send-start and send-complete UTC plus monotonic timestamps, byte count and the matching intent event_id. This is not proof that the device received or applied the frame.
- `frame_tx_error`: partial/failed write, exception, byte count known/unknown, and related intent event_id. A partial frame is never relabeled as sent successfully.
- `frame_rx`: every complete received frame, exact raw COBS bytes including delimiter, receive-start/receive-complete UTC and monotonic timestamps, CRC/COBS/length validation results, and parsed header fields only when safe to parse.
- `frame_rx_fragment` / `frame_rx_discard`: incomplete bytes, overflow, framing loss and parser discard events, including byte count and reason. Do not invent a complete frame.
- `command_ack_match`: links one transmitted intent/complete event to the exact ACK frame by session tag, epoch tag, command_id and expected ACK type; records match, timeout, duplicate, mismatch or unsolicited status.
- `sample_context_map`, `adc_batch_received`, `status_received`, `transport_gap`, `protocol_error`, `session_open`, `session_close`, `allocator_commit`, and `artifact_error` retain the event-specific fields already specified in §12.5 plus the correlations needed to join them.

For STOP, record both header `command_id` and payload `stop_request_id`; never collapse them into one identifier. Record all STOP retries and ACKs independently.

### A3.2 Append, flush and crash recovery

- Each JSONL event is serialized as one UTF-8 JSON object followed by exactly one LF. A line is immutable after append.
- Before any command bytes are sent, append `frame_tx_intent`, flush userspace buffers, and fsync the evidence file. If this fails, do not send the command.
- After each complete received frame (or fragment/discard event), append and fsync before allowing the parser to discard its only copy. If fsync fails, mark the session evidence-failed, issue STOP if the transport remains usable, and prohibit further nonzero PWM commands.
- After a command write completes or fails, append its completion/error event and fsync. An intent without completion is recovered as outcome-unknown, not assumed unsent or successful.
- On startup, scan the JSONL file from byte zero. Validate UTF-8, JSON, required fields and LF boundaries. A malformed/truncated final line is preserved byte-for-byte in a recovery segment and recorded as a torn-tail event in a new recovery log; never silently truncate or rewrite the original artifact.
- Use a monotonically increasing host event_seq per artifact in addition to UUID event_id. Gaps, duplicates and out-of-order sequence values are integrity errors.
- No heap of unflushed events is permitted to grow without a fixed bound. If disk or fsync latency causes acquisition/serial backpressure, the host must STOP and mark the measurement incomplete rather than drop evidence silently.

### A3.3 Manifest, hashes and package closure

At orderly finalization, create a manifest containing schema/version, measurement_session_id, full verified device_epoch_id or null, file names, byte lengths, event counts, first/last event_seq, SHA-256 of each artifact, completion status, and any evidence gaps. Hash the exact final bytes, including LF delimiters. The manifest itself is serialized canonically and hashed in a detached package index; avoid a self-referential hash.

The package is finalized by writing temporary manifest/index files, fsyncing them, atomically renaming them, and fsyncing the containing directory. A package is complete only when RawLog, transport-evidence and manifest hashes verify and the manifest says complete. A crash before finalization leaves an explicitly incomplete package; it is never auto-promoted to complete. A recovery process may append recovery events and generate a new manifest version referencing the prior manifest hash; it must not rewrite prior artifacts.

### A3.4 Retention and missing-evidence policy

Proposed retention target: retain the complete session package for at least 10 years from session close, subject to project storage/privacy policy approval. Keep at least one independently verified backup copy; verify hashes on backup creation and periodic restore checks. If retention or backup policy is not approved, mark it as an unresolved package requirement rather than assuming archival durability.

Missing command intent, missing ACK correlation, fsync failure, hash mismatch, missing sidecar, truncated tail, or missing manifest makes the package `evidence_incomplete`. RawLog samples may still be retained as raw observations, but the run cannot be represented as a complete, loss-auditable 310 measurement or used as complete teacher evidence. No missing event is reconstructed from timestamps or inferred state.

## A4. EEPROM lifetime target and power-failure evaluation

Adopt the following **design target for review**, not a proven product-life claim:

- Maximum expected boot events: 10 per calendar day.
- Required service interval: 10 years.
- Required boot count: 10 × 365.25 × 10 = 36,525 boots (round up to 36,600 for acceptance budgeting).
- Journal system-level rotation estimate: up to 800,000 boot events before a marker cell reaches 100,000 write/erase cycles, assuming 16-slot even rotation and two marker writes per slot visit. For the 36,600-event target, each marker cell sees at most 4,575 writes (73,200 marker writes summed across all slots); each payload cell sees at most 2,288 writes. These are per-cell versus aggregate counts as distinguished in §A4; conditional arithmetic only, not a service-life guarantee.

Power and write failure requirements:

1. Configure and verify a brown-out reset threshold appropriate to the actual board supply and MCU clock. A candidate ATmega328P BOD level is 4.3 V for a nominal 5 V Uno design, but this is not assumed to be configured on the existing board. Fuse configuration and board-specific supply tolerance must be independently verified before implementation.
2. Do not start a journal write when supply voltage is below the approved safe-write threshold. The threshold and measurement method must be specified from the selected MCU datasheet and board power design; an ADC estimate alone is not a substitute for BOD.
3. Keep the target slot's commit marker invalid until payload and CRC have been written and read back. Commit marker is the final write. On reset, only slots with valid magic/version, CRC and committed marker are candidates.
4. If power fails before marker commit, the prior valid generation remains authoritative. If the marker is committed but subsequent verification fails, boot identity is invalid; fail closed. Never guess which generation was intended.
5. Test power interruption at every byte-write boundary, during marker invalidation, each payload byte, CRC, marker commit, and readback. Verify that boot selects either the previous fully valid record or the new fully valid record, never a partially written identity.
6. Repeated brownout/reset loops must not cause unbounded EEPROM writes. A failed boot identity write must enter BOOT_ID_INVALID and require maintenance/recovery; no automatic retry loop that consumes endurance.
7. Count actual committed boot increments in the journal evidence when possible. The 10/day assumption must be reviewed against expected user operation; if measured/expected boot rate exceeds it, recalculate the lifetime budget before approval.

The 10-year/10-boots-per-day target is a proposed project requirement awaiting commander confirmation. The earlier multi-century arithmetic examples are withdrawn as product-life statements.

## A5. 20 Hz cadence: explicit non-adoption and qualification method

20 Hz/channel remains **not adopted**. No threshold statistic or resistance input may assume it is adequate.

Before cadence selection, the design authority must provide or approve:
- ACS712 variant, sensitivity, bandwidth and output noise characteristics;
- motor PWM frequency and PWM duty behavior at values 0–30;
- analog input network, anti-alias low-pass filter topology and measured transfer function;
- expected current signal bandwidth and the frequency components relevant to the selected low-frequency statistic;
- settling interval after each PWM transition and after ADC multiplexer/channel switching;
- threshold decision statistic (e.g. fixed-window mean, median, trimmed mean or dispersion) and its required uncertainty/confidence;
- required detection probability and acceptable false-positive/false-negative rate near the threshold.

Qualification proposal:

1. Define the statistic and window before collecting comparison data; do not select it after seeing favorable results.
2. Obtain a separately authorized high-rate reference capture with sufficient bandwidth and anti-alias filtering to characterize PWM ripple and commutation components. This is a future controlled experiment, not authorized by this document.
3. Compare candidate 20 Hz samples against the reference statistic over the same settled windows and all PWM levels around the expected detection threshold.
4. Quantify bias, repeatability, variance, aliasing sensitivity to sampling phase, and probability of misclassifying the threshold. Include worst-case PWM phase alignment and channel-switch settling.
5. Accept 20 Hz only if the predeclared uncertainty and classification criteria are met. Otherwise choose a higher rate, a different analog filter/statistic, or a dedicated hardware averaging approach and revise the byte/throughput/SRAM budget.
6. Until this qualification is approved, cadence is an open design variable. The current 20 Hz schedule is an arithmetic/transport candidate only, not a measurement-quality claim.

## A6. Uno SRAM, bounded scheduling and STOP identifier semantics

### A6.1 Provisional static memory budget

The following is a conservative allocation proposal for an ATmega328P Uno with 2,048 bytes SRAM. It is a planning budget, not compiler evidence:

| Allocation | Reserved bytes | Design constraint |
|---|---:|---|
| Single in-place decoded/COBS TX frame workspace (largest ADC_BATCH) | 194 | One frame buffer only; ADC batch payload is assembled directly into this workspace; no duplicate batch array |
| RX frame parser workspace | 40 | Device receives only host frames up to HELLO/STOP request maximum; oversize frames are drained/discarded with bounded parser state |
| HardwareSerial RX + TX rings | 128 | Assumes 64 bytes each; actual core build allocation must be verified |
| STOP history (4 fixed entries) | 32 | 8 bytes/entry; no dynamic allocation |
| Recent ARM/PWM command cache (4 entries) | 48 | 12 bytes/entry; exact cached ACK may be regenerated from fixed fields; no heap |
| Protocol/session/state/counters | 96 | Fixed-width fields only |
| ADC scheduler/channel/timestamp state | 64 | Fixed-width fields only |
| Error/status scratch and parser state | 48 | Bounded, fixed-size |
| **Subtotal planned static allocations** | **650** | No duplicate 173-byte batch buffer |
| Reserved worst-case stack budget | 384 | Must be verified by stack watermark or static call-depth bound |
| Reserved safety margin | 256 | Not allocatable by features |
| **Total planned** | **1,290** | **758 bytes remain unallocated** |

No dynamic allocation, Arduino `String`, recursion, variable-length arrays, or unbounded local arrays are permitted in acquisition, parser, scheduler, STOP or TX paths. All structures use fixed-width integer types and compile-time sizes. The 194-byte frame workspace must be encoded in place with bounded COBS operations; if the selected COBS implementation requires a second full frame buffer, this budget is invalid and design must return for revision.

This budget is not a claim that the current firmware fits. Before implementation approval, provide compiler map/sizeof output for every row, confirm the actual HardwareSerial ring sizes and library/core version, measure worst-case stack high-water under nested parser/STOP/CRC/COBS/TX paths, and show the final linker SRAM total. Any static overrun, stack intrusion into the 256-byte margin, or unbounded heap use fails the gate.

### A6.2 TX ownership and bounded service

There is one TX frame workspace. The producer builds a complete frame in that workspace, marks it READY, and TX becomes its sole owner until the final delimiter is accepted by the UART. No other frame may interleave. The main loop writes only `min(availableForWrite(), configured_chunk_max)` bytes per service pass and then returns to command parsing/STOP checks. The configured chunk maximum must be small and fixed (candidate 16 bytes).

STOP parsing and the immediate software output-zero request do not wait for the TX frame to finish. If a frame is already partially transmitted, it completes atomically before STOP_ACK can use the same workspace; STOP_ACK is queued at highest priority immediately afterward. STOP does not wait for an ADC batch to be assembled or transmitted. The implementation must not disable interrupts during a full frame write.

Acquisition may continue only while the fixed workspace/producer state can retain every required sample attempt. If TX backpressure prevents retention, increment loss_counter for every unretained attempt, preserve sequence progression, and keep servicing STOP. Do not overwrite TX-owned bytes. If loss exceeds the approved measurement acceptance threshold (to be defined), the host marks the run incomplete. A permanently blocked UART cannot be solved by software scheduling; after the approved timeout the host sends STOP if possible and records link failure. Physical protection remains a separate hardware requirement.

### A6.3 STOP header command_id versus payload stop_request_id

These identifiers have different scopes and MUST remain distinct:

- Header `command_id`: uint32 transport command correlation/freshness ID. For STOP_REQ it is nonzero and monotonically increasing within the active host session, like other command-bearing frames. It correlates the request frame with its STOP_ACK and is included in transport evidence.
- Payload `stop_request_id`: uint16 safety-request identity maintained by the host. It is allocated per logical STOP action and remains unchanged across retries of that logical STOP. A new independent STOP action receives a new ID.
- Exact retry: retransmit the byte-identical STOP_REQ frame, preserving both identifiers. Device returns the cached/recorded outcome when available.
- Reframed retry: if the host must issue a new command_id for the same logical stop, it must retain the same stop_request_id. Device history classifies it as a duplicate only when requester/session relation, stop_request_id and stop_reason match; otherwise same stop_request_id with different reason is ID_CONFLICT. The ACK carries the header command_id of the received frame and the recorded request_outcome.
- New logical STOP: new stop_request_id and new command_id. STOP action is idempotently attempted regardless of history capacity or stale session. History exhaustion affects duplicate auditability, never whether output-zero is requested.
- Device duplicate key is (verified boot_id64, requester session tag if known, stop_request_id). It separately stores stop_reason and the first observed header command_id for diagnostics. Header command_id alone does not define logical STOP identity.
- Header command_id freshness is checked for correlation, but the STOP safety exception means a valid STOP_REQ is acted upon even if the command_id is stale/regressed. Such a frame is recorded as stale-command evidence; it cannot clear STOP or cause drive.

STOP_ACK correlation is therefore two-dimensional: echoed header command_id identifies the transport attempt, while payload outcome and stop_request_id in the evidence identify the logical safety request. The current three-byte STOP_ACK payload remains unchanged; adding stop_request_id to STOP_ACK would require a separate protocol revision and length review.

## A7. Updated correction matrix

| Review finding (2026-11-02) | Integrated response |
|---|---|
| 1. Host restart may reuse session tag | §A1: durable never-reuse uint32 allocator, fail-closed journal, no wrap/collision fallback |
| 2. uint16 device sample sequence rollover | §A2: continuous per-boot counter, host-side extended monotonic uint64 in existing RawLog field, original wire value in sidecar |
| 3. Companion artifact lacks outbound commands and durability | §A3: TX intent/completion/error, all RX frames/fragments, ACK correlation, fsync rules, recovery, manifest/hash, backup and retention proposal |
| 4. EEPROM life assumptions unspecified | §A4: proposed 10 boots/day × 10 years target, 36,600 budget, brownout/write interruption test requirements |
| 5. 20 Hz not qualified | §A5: explicitly not adopted; required signal inputs and predeclared comparison qualification method |
| 6. SRAM/TX/STOP identifiers incomplete | §A6: 650-byte static allocation proposal, 384-byte stack reserve, 256-byte margin, bounded TX service and distinct command_id/stop_request_id semantics |

## A8. Approval boundary after this addendum

This addendum resolves the six findings at the level of a concrete design proposal, not implementation evidence. The following remain evidence gates: host allocator crash/restore tests; sequence rollover and long-session tests; sidecar fsync/crash/manifest/restore tests; EEPROM datasheet/fuse and power-interruption verification; sampling qualification; compiler-backed SRAM/stack measurements and TX-backpressure/STOP scheduling tests. All such tests and implementation work require separate authorization.

PR #183 must remain Draft, open and unmerged. No Python or firmware edits, compilation, upload, serial connection, motor energization, 310-second measurement, formal design acceptance or 310-5 transition is authorized by this revision.


---

## A9. Re-review closure: normative host-side contracts and approval split

This section converts the six remaining review conditions into testable design contracts where possible, without claiming implementation evidence. It supersedes conflicting proposal wording in A1–A8; unresolved approvals remain unresolved.

### A9.1 Session-tag allocator: normative failure and recovery behavior

The host allocator MUST bind its durable journal to one installation namespace. The full measurement_session_id UUID is authoritative; the 32-bit session tag is correlation only.

1. A tag is durably committed as consumed before any HELLO carrying it is transmitted. A crash after commit but before transmission burns the tag.
2. Allocation success requires journal/checkpoint durability. Uncertain commit status consumes the tag; it MUST NOT be retried.
3. After process restart, load and validate the same namespace and journal. Missing, corrupt, unrecoverably truncated, rolled-back, or namespace-mismatched state MUST fail closed. No random/time-derived fallback is allowed.
4. Restore/migration preserves namespace and highest committed allocation. If rollback cannot be excluded, quarantine the old namespace; provision a new one only through explicit maintenance/recovery. Never resume a session under a possibly reused tag.
5. Allocatable tags are 1..0xFFFFFFFE; 0 and 0xFFFFFFFF are reserved. Exhaustion is a hard stop; wrap is forbidden.
6. Duplicate HELLO retry is allowed only with the same allocated tag and byte-identical challenge/frame. Every new measurement session receives a new tag.

Host acceptance vectors: crash at every journal write/flush/rename boundary; committed-but-unsent allocation; corrupt/missing journal; older backup restore; namespace mismatch; final tag and exhaustion; concurrent allocations. Every vector must demonstrate no duplicate allocation and fail-closed behavior when uniqueness cannot be proven. These are future implementation tests, not authorized now.

### A9.2 RawLog sequence expansion: continuity and ambiguity contract

The host sequence expander maintains a durable checkpoint keyed by the verified full device_epoch_id, never the 32-bit epoch tag alone. It stores the last accepted uint16 wire sequence, expanded monotonic value, and evidence references for replay/conflict detection.

- A new verified boot epoch starts a new expansion namespace. Sequence reset is valid only after HELLO verifies a different full boot identity. A low-32-bit tag by itself cannot prove epoch identity.
- Within one verified epoch, counting is continuous across HELLO, ARM, STOP, measurement sessions, and host process restarts. The device does not reset the counter at those boundaries.
- Modular delta d=(wire-last_wire) mod 65536: d=1..32767 is forward; d=0 is a duplicate candidate accepted only with exact matching frame/sample evidence; d=32768..65535 is ambiguous/backward and MUST NOT be guessed.
- For forward progress, expanded sequence increases by d. Gaps are recorded; no synthetic RawLog samples are created. Accepted unique values are strictly increasing and stored in existing RawLog v2 device_sample_sequence; no schema change.
- Checkpoint progress must be durable before package recovery/completion. If checkpoint/evidence is absent, corrupt, conflicting, or the outage could exceed the ambiguity bound, affected samples remain unresolved and the package is sequence_incomplete/evidence_incomplete. No rebasing by guesswork.
- Unverified-epoch samples remain transport evidence only.

Host acceptance vectors: 65535→0 rollover; exact and conflicting duplicates; forward gaps; d=32767 and d=32768; crash around checkpoint commit; absent/corrupt checkpoint; ambiguous outage; verified reboot; low-32-bit epoch-tag collision. Define each expected outcome as accepted, deduplicated, unresolved, or package-incomplete.

### A9.3 transport-evidence: Python durability, deadline and package contract

1. Before any command write, append and durably commit frame_tx_intent with exact bytes and correlations. Only then may serial write begin.
2. Record and durably commit frame_tx_complete or frame_tx_error. Completion means accepted by the host serial API, not device receipt/application.
3. Every received byte range is represented by a complete frame, fragment/discard, or explicit receive-loss event. An ACK cannot advance the sequence until raw bytes and ACK-match evidence are durable.
4. ARM/PWM ACK matching requires expected response type, exact session/epoch correlation, command_id and applicable context/result. Timeout or missing ACK is unknown outcome; do not mark stage applied or advance its start timestamp. Retry byte-identically with same command_id or enter defined abort/STOP path.
5. Any required evidence append/fsync failure prohibits further nonzero PWM. If transport remains usable, issue STOP through the emergency path; record possible STOP evidence failure. Run is incomplete, never complete.
6. Evidence fsync is synchronous at command and frame-acceptance boundaries; it cannot be silently deferred beyond a stage transition/command decision. If fsync latency misses a stage deadline, do not backdate or fabricate timing: STOP if possible, record deadline overrun, and mark incomplete. The maximum fsync latency budget is a host performance requirement still to be measured.
7. Package finalization requires durable RawLog, evidence, sequence checkpoint, and manifest/hash verification. Missing intent, ACK correlation, RX coverage, checkpoint, manifest, or failed hash yields evidence_incomplete. Recovery cannot retroactively make an interrupted run complete.

Host acceptance vectors: fail each append/fsync; partial serial write; crash between intent/write, during write, after write/before completion event, after RX/before fsync, and during manifest commit; timeout/late ACK; fsync beyond deadline; torn JSONL recovery. Prove no false stage completion, no nonzero PWM after evidence failure, no fabricated duration, and incomplete classification.

### A9.4 Explicit approval register

| Item | Status | Decision/evidence required | Authority/gate |
|---|---|---|---|
| EEPROM operating target | Proposed 10 boots/day × 10 years = 36,600 events | Confirm service target or provide approved target and recalculate endurance | 310司令塔 policy decision |
| EEPROM electrical behavior | Unverified | Exact MCU/board, supply envelope, BOD fuse, datasheet write conditions, safe-write threshold and power-interruption results | Hardware approval before implementation/test |
| 20 Hz/channel cadence | Not adopted | Sensor variant/sensitivity/bandwidth, PWM frequency, analog filter, settling, statistic, uncertainty/classification limits; qualify against reference capture | Measurement design approval; reference experiment separately authorized |
| SRAM/scheduling | Planning estimate only | Compiler/map/sizeof, actual serial rings, stack high-water, bounded TX/backpressure and STOP evidence | Implementation authorization then verification |
| Evidence retention | Proposed ≥10 years and one verified backup | Approve retention, backup/restore policy, storage capacity | Data-retention authority |
| Loss acceptance threshold | Undefined | Define allowed loss by channel/window and whether loss invalidates threshold/resistance evidence | Measurement design authority |
| Host fsync latency budget | Undefined | Set maximum latency/jitter compatible with stage deadlines and stop/incomplete response | Python sequence design approval |

### A9.5 Disposition and authority boundary

A9.1–A9.3 define proposed normative host contracts and test vectors, not implementation proof. A9.4 lists decisions and qualification items still outstanding. Design remains conditionally returned for continued review. PR #183 MUST remain Draft, Open and Unmerged. No Python/firmware edits, compilation, upload, serial communication, motor energization, 310-second measurement, formal acceptance, or 310-5 transition is authorized. HARDWARE_CURRENT_LIMIT_CONFIRMED=false.

# 310-4 Design Finalization Package — 2026-11-02

**Authority:** 司令塔「310-4 設計審査完遂指示書」  
**Status:** Finalized design-review submission; not formal acceptance and not implementation authorization.  
**Precedence:** Issue #35 remains the project specification authority. Accepted 310-1/2/3 contracts are preserved. No RawLog v2 public-schema change is proposed.

## F1. Binding requirements incorporated

The following are binding project requirements, not approval of a specific implementation mechanism:

1. EEPROM boot-identity journal endurance budget: 36,600 boot events (10/day × 10 years, rounded up).
2. Transport Evidence retention: at least 10 years.
3. At least one independent, verified backup copy.
4. No undetected data loss is acceptable.
5. Loss must be recorded by channel and time window.
6. TX backpressure must not prevent STOP processing/output-zero request.
7. Buffer ownership, occupancy/high-water and overflow/loss must be distinguishable.
8. SRAM assessment includes static data, core/library buffers and worst-case stack.

These requirements do not approve a board, fuse setting, storage device, sampling rate, queue implementation, backup product or physical safety design.

## F2. Technical determinations

### F2.1 EEPROM

The candidate journal has 16 slots × 16 bytes. For 36,600 committed boots, rotation distributes about 2,288 generations per slot. Each slot visit invalidates and then commits its marker (about 4,576 marker write operations per slot over the target interval); each payload byte is rewritten about 2,288 times, subject to EEPROM update semantics and retries.

This is a write-count budget, not a lifetime guarantee. Exact MCU marking, datasheet endurance conditions, fuse bytes, board revision, supply envelope and power-fail behavior are not in the reviewed evidence. No BOD threshold is selected. The 4.3 V candidate in A4 remains unverified.

Write order: invalidate target marker; write payload and CRC; read back and verify; commit marker last; verify. Boot accepts only valid magic/version, CRC and committed marker. Ambiguous writes preserve the previous valid generation or enter BOOT_ID_INVALID. No identity is synthesized and no unbounded retry loop is allowed.

**Determination:** 36,600 events is the adopted design budget. Electrical feasibility and service life remain unproven pending exact MCU datasheet conditions, fuse configuration, power envelope and power-interruption evidence.

### F2.2 Sampling cadence and 20 Hz

20 Hz/channel remains NOT ADOPTED. The candidate schedule (scans at T and T+25 ms, repeated every 100 ms) yields alternating 25 ms/75 ms intervals per channel, with a long-run average of 20 conversions/s/channel and 10 ADC_BATCH/s. It is non-uniform, not an equally spaced 20 Hz sample train, and does not establish measurement bandwidth or threshold validity.

For a nominal 16 MHz ATmega328P using ADC prescaler 128, ADC clock is 125 kHz and a normal 13-clock conversion is approximately 104 µs. Six conversions have nominal conversion-core time around 0.62 ms per scan, excluding mux settling, software, timestamps and interrupts. This is clock arithmetic, not measured performance or proof of the installed firmware configuration.

The 25/75 ms periodic non-uniform schedule has no single uniform-sampling Nyquist frequency; do not apply a 10 Hz Nyquist claim. It cannot characterize PWM ripple or commutation transients from this average rate. Suitability for a low-frequency statistic requires sensor variant/bandwidth, PWM frequency, analog filter transfer function, channel and stage settling, sampling phase, statistic and uncertainty limits, followed by an authorized reference comparison.

**Determination:** no sampling rate is approved. 20 Hz is only a transport/arithmetic candidate.

### F2.3 ADC order, timestamps and failures

Candidate scan order remains A0, A1, A4, A5, A2, A3. These are six distinct conversions. Each gets its own timestamp and context snapshot. device_timestamp_point=conversion_midpoint means capture micros immediately before starting analogRead and immediately after completion, then compute modular midpoint. On a conventional 16 MHz Uno, micros quantization is 4 µs. uint32 micros wraps after about 71.6 minutes; unwrap only within one verified full device_epoch_id and modular gaps below 2^31 µs.

Standard analogRead returns an ADC code and exposes no per-conversion hardware error status. A disconnected/floating input may still return a numeric value. A timeout status is valid only for a bounded conversion implementation with a verified timeout. Distinguish not-acquired from attempted-but-invalid. ADC raw zero is not a missing marker.

**Determination:** one conversion = one ADC_SAMPLE. Preserve raw value, individual timestamp, channel, sequence, epoch and stage context. Do not claim sensor-disconnect detection from ADC code alone.

### F2.4 UART

57600 baud, 8N1 has theoretical capacity 5,760 bytes/s. Existing wire maxima:
- ADC_BATCH: 194 bytes × 10/s = 1,940 B/s.
- STATUS baseline: 31 B/s.
- APPLY_ACK: 25 × 31 / 310 = 2.5 B/s.
- Nominal subtotal: 1,973.5 B/s, about 34.3% of theoretical capacity.
- One 194-byte ADC_BATCH occupies about 33.7 ms on the wire.

This excludes handshake, STOP, ERROR, bursts, retries, USB scheduling and service gaps. It is not a worst-case latency guarantee. Preserve whole-frame non-interleaving and priority: STOP/fault, command ACK/session-critical status, ADC_BATCH, diagnostics. TX owns its buffer through the final delimiter. Bounded chunks must return control to command parsing/STOP service; STOP must not wait for batch completion or TX drain.

**Determination:** frame-size and average-throughput arithmetic is consistent. Queue capacity, worst-case latency and physical STOP response are not established.

### F2.5 SRAM and buffers

Existing A6.1 planning budget: 650 bytes static allocation + 384 bytes stack reserve + 256 bytes safety margin = 1,290 bytes against 2,048 bytes, leaving 758 bytes unallocated. It assumes one in-place 194-byte frame workspace, 40-byte RX parser, 128-byte serial rings, fixed caches and no dynamic String/heap in critical paths.

This is not measured static usage. Compiler/map/sizeof must verify each row and actual core ring sizes. Stack reserve must be checked under worst nested parser/CRC/COBS/STOP/TX path. Buffer ownership must expose FREE/FILLING/READY/TX_OWNED, occupancy/high-water and overflow. Every unretained attempt must be counted by channel and time window. TX-owned bytes may never be overwritten.

**Determination:** 650/384/256 remains provisional; SRAM acceptance requires compiler map, core allocation, stack high-water/bound, heap evidence and backpressure/STOP test.

### F2.6 fsync and schedule

310-3 stage timing remains unchanged: stage starts at host receipt of matching apply ACK; prior stage ends at host send time of next-stage command. Evidence fsync is on the host critical path and cannot be backdated or excluded.

No numeric fsync budget can be inferred from a 10-second stage. Measure p50/p95/p99/max and failures on the approved target storage under representative load, including file and directory fsync. Until a maximum is approved, fsync crossing a stage deadline means no fabricated timestamp: STOP if possible, mark incomplete, do not advance.

If TX intent cannot be fsynced, do not send nonzero PWM. If RX evidence cannot be persisted, do not accept ACK/sample as durable; prohibit further nonzero PWM and attempt STOP through the emergency path. A STOP attempt that cannot itself be recorded remains uncertain.

**Determination:** failure behavior is defined; numeric latency budget and target-storage performance remain unverified.

### F2.7 Evidence, recovery and loss

RawLog v2 public package remains exactly manifest.json + records.jsonl, append-only and manifest-last. Transport Evidence is a separate companion artifact. It records exact TX/RX bytes, fragments/discards, timestamps, intent/completion/error, ACK matches, sequence/loss observations, allocator/checkpoint events and artifact failures.

Finalization requires RawLog, Evidence, sequence checkpoint and manifest/index hashes to verify. No-undetected-loss means any unaccounted sequence gap, missing byte range, fsync failure, missing sidecar/checkpoint, hash mismatch, torn tail or unverified backup yields incomplete/evidence_incomplete. Never synthesize missing samples/events.

Distinguish: attempted conversion failure; attempted but unretained conversion; lost/discarded batch/frame; host receive gap/unknown bytes; Evidence persistence failure; unresolved loss. Aggregate counter alone is insufficient: channel and time-window dimensions are binding and belong in companion Evidence only, not RawLog v2. Window duration remains a design input.

Recovery preserves originals byte-for-byte, does not truncate/repair records, does not synthesize PWM_STAGE/ADC_SAMPLE, publishes manifest last and retains work until all artifacts are verified. One independent backup is required; verification includes hashes and restore/readability, not merely successful copy.

## F3. 310-1 through 310-3 compatibility

| Contract | Source | 310-4 disposition |
|---|---|---|
| ADC_SAMPLE = one conversion | 310-1 / #170 | Preserved; each 12-sample batch expands to 12 independent records |
| device_timestamp_point=conversion_midpoint | 310-1 | Preserved; individual conversion midpoint |
| device_epoch_id full identity | 310-1 + 310-4 handshake | Full boot identity authoritative; low 32-bit tag is correlation only |
| device_sample_sequence monotonic | 310-1 | Host expands uint16 wire sequence per full epoch; no schema change |
| stage_context_id fixed at acquisition | 310-1 / #170 | Device snapshots token immediately before conversion; host maps by session + full epoch |
| Python owns 31 stages | 310-3 | Preserved; no Arduino 310-second scheduler |
| command sent ≠ ACK ≠ physical state | 310-1/3 | Preserved |
| RawLog package/recovery | 310-2 | Public two-file package unchanged; Evidence is separate companion artifact |
| Incomplete work not complete | 310-2/3 | Preserved; no synthetic records |

No accepted RawLog v2 fields, types, record semantics or public package structure are changed. Any schema change requires a separate Issue #35 proposal.

## F4. Authority boundary

36,600 EEPROM events, ≥10-year Evidence retention, one independently verified backup, zero undetected loss, channel/window loss records, STOP independence from TX backpressure, explicit buffer ownership/occupancy/overflow and stack-inclusive SRAM evaluation are binding requirements. They do not approve a hardware configuration or prove implementation.

20 Hz remains unadopted. BOD/fuse/supply conditions, numeric fsync budget, loss-window duration, exact storage/backup mechanism and compiler-backed SRAM/stack results remain open. This finalization authorizes no implementation or physical test.


# 2026-11-02 最終完遂追補（旧記述と矛盾する場合は本節が優先）

## A. MCU・EEPROM・耐久性

設計基準はATmega328P / ATmega328/Pとする。公式根拠はAtmel-42735B-ATmega328/P Datasheet Complete, 11/2016。URL: https://docs.arduino.cc/resources/datasheets/Atmel-42735-8-bit-AVR-Microcontroller-ATmega328-328P_Datasheet.pdf 。該当箇所: §2（EEPROM 1,024B、SRAM 2,048B）、§12.4–12.4.2（EEPROM）、§15.5（BOD）、§31.2（fuse）、§32.3（speed grade）、§32.5（BOD threshold）、§28.1–28.5（ADC）。

UNO R3相当基板の実搭載チップのマーキング・signature・revisionは未確認。ATmega328Pを実機確認済みと記載しない。実機受入でtop marking、signature bytes、基板revision、clock sourceを採取し、異なる品種なら再審査する。

EEPROMは1,024 bytes、byte-addressable。耐久値は少なくとも100,000 write/erase cycles per EEPROM cellであり、slot/device単位の回数ではない。CPU byte programmingは26,368 calibrated RC oscillator cycles、typical 3.3ms。3.3msはtypicalで最大保証値ではない。書込みはEEPE clear待ち、EEAR/EEDR設定、EEMPE set後4 CPU cycles以内にEEPE set、完了までEEPE clear待ち。EEMPE/EEPE間に割込みを許さない。低VCCではEEPROMだけでなくCPU誤実行も起き得る。データシートは耐久値について全電圧・全温度の個別試験条件を網羅した表やbyte-write atomicityを規定していないため、100,000回から全条件の寿命保証・電源断保証を推定しない。実チップ製造元/revisionの仕様・clarificationと実際の電源条件を受入時に確認する。

16-slot方式はslot 16B×16=256B。1 slotあたりmarker 1B、payload 15B。各eventでmarker INVALID、payload/CRC書込み、readback/recompute、marker COMMITTEDの順とし、最悪2 marker writes/visit、1 payload write/cell/visitで計算する。36,600 eventsでは各slot visitは2,287または2,288回。marker各cell最大2×ceil(36,600/16)=4,576 writes、payload各cell最大2,288 writes。全marker cells合計は2×36,600=73,200 operations。これはaggregateでありper-cell ratingではない。100,000/4,576=21.85倍、100,000/2,288=43.71倍の単純算術余裕。100,000×16/2=800,000 eventsは均等輪番の理想算術上限であって寿命保証ではない。36,600は10 events/day×365×10 years。slot別write counterを保持し、上限超過前にBOOT_ID_INVALIDへfail-closedする。

## B. BOD・fuse・電源断

§32.3の20MHz speed gradeはVCC 4.5–5.5V。設計では16MHzも保守的にVCC下限4.5Vとする。§32.5 BODLEVELは1.8V設定 min1.7/typ1.8/max2.0V、2.7V設定 min2.5/typ2.7/max2.9V、4.3V設定 min4.1/typ4.3/max4.5V。よって4.3V BOD単独では16MHz/4.5Vを保証しない。min 4.1Vの個体では4.5V未満までresetしない可能性がある。

設計決定: BODは無効化しない。4.3V設定は補助監視候補とするが、16MHz下限4.5Vを保証する唯一の保護にはしない。外部voltage supervisorを必須要素とし、全温度・全公差におけるfalling thresholdの最小値が4.5V以上の品種/設定を選ぶ。監視点はMCU VCC pin近傍、reset recovery delayとhysteresisも確認する。EEPROM write中の電源断にはpower-fail検出とhold-upを設け、既開始writeを完了できるようにする。容量は実負荷、ESR、最悪write time、温度、公差から決め、typical 3.3msを保証値として使わない。最悪条件でhold-upを保証できない基板はinternal EEPROM-only identity storeを採用せず、外部NVM等の再審査までBOOT_ID_INVALID/ARM禁止とする。

Fuse方針: CKSEL/SUTは実装16MHz crystal/resonatorに整合、CKDIV8 unprogrammed、BODLEVELは補助4.3V候補、RSTDISBL unprogrammed、SPIEN programmed、WDTON always-on fuseは不採用。EESAVE/BOOTRST/BOOTSZはbootloader/EEPROM保全方針に整合。hex値を推測で固定しない。実機でlow/high/extended fuse全byteをread-backする。fuse変更は別承認事項。

journal順はINVALIDATE→payload+CRC→readback/recompute→COMMIT marker last→verify。起動時はmarker、magic/version、CRC、generation continuityすべてvalidなrecordだけ採用。ATmega328P datasheetはbyte write中断時atomicityを保証しない。CRC/markerは検出を強めるが全torn patternを数学的に排除しない。曖昧recordはBOOT_ID_INVALID。BODは短いdipを見逃し得る（tBOD typical 2µs）。RESETはMCUを止めてもdriver power stageを遮断しない。MCU freeze/reset時は外部pull-down/enable gatingと独立power cutoffが必要であり、ソフトウェアSTOPだけで安全を保証しない。

## C. SRAM・STOP

ATmega328P SRAM総量2,048B。実装受入上限をstatic/global≤650B（HardwareSerial ringを含む）、worst stack≤384B、未使用protected reserve≥256B、合計≤1,290Bに固定する。残り758Bは未割当て余裕で、追加バッファ枠ではない。最大wire frame 194B、RX parser≤40B、TX workspaceはsingle in-place 194B buffer。ADC stagingは最大173B payload。TX_OWNED bufferは変更禁止。dynamic String/new/malloc/heap growthはprotocol/STOP/ADC critical pathで禁止し、原則起動後heap allocationなし。650/384/256は設計上限であって実測値ではない。compiler map/avr-size/linker symbols、全structure/buffer sizeof、HardwareSerial ring実サイズ、worst nested parser/CRC/COBS/ADC/TX/STOP/ISR stack watermarkで確認する。static>650、stack>384、reserve<256、heap/stack collision、overflowはFAIL。

STOP優先順位はSTOP latch first（不可逆）、PWM output=0、全direction output LOW、active ARM/command permission invalidation、state STOP_LATCHED、最後にACKを送信queueへ登録。出力操作はTX drain、availableForWrite、ACK、ADC batch完成に依存しない。すでにTX_OWNEDのframeはinterleave防止のためframe boundaryまで送信してよいが、STOP latch/output actionを待たせない。STOP handlerはbounded RX pathで処理しheap allocationやframe生成をしない。MCU freeze/reset、GPIO high-Z、driver fault、MOSFET short、電源断/配線故障には外部driver enable pull-down、独立watchdog/supervisor gating、power cutoffが必要。STOP_ACKは物理停止証明ではない。

## D. ADC周期・測定精度

役割は固定: A0=ACS712 #1 winding current唯一の正式入力、A1=ACS712 #2独立brush-stability観測、A2/A3 reference only、A4/A5 independent raw voltage。A0/A1平均・代替は禁止。A4/A5を差分に置換しない。20Hz候補未採用。T/T+25ms/T+100msは同一channelで25ms/75ms交互の非等間隔でありuniform 20Hzではない。

ATmega328P ADCは10-bit、0.5LSB INL、±2LSB absolute accuracy、入力0–VCC、AVCC/AREF/internal 1.1V reference、normal conversion 13 ADC clocks（first conversion 25 clocks）。channel/reference changeは次conversionから反映。source impedance/sample-hold settlingを別評価し、reference切替直後の最初のconversionはdiscard。AVCCはVCC±0.3V以内、AREF decouplingを守る。例としてVREF=5.000VならLSB=5/1024=4.8828mV、ADC ±2LSB contribution=±9.7656mV。これはVREF実測値でもsystem accuracy保証でもない。reference tolerance、AVCC ripple、ground shift、sensor offset/sensitivity, noise, filter, mux settling, PWM phase, thermal driftを加える。

ACS712 exact suffix/range/filter未確認。型番でsensitivity/bandwidth/offset/noise/driftが異なるため型番・datasheet・実測VREF・zero-current offset calibration・traceable current reference gain/linearity calibrationなしにraw ADCをampere換算しない。A0/A1は個別校正し、独立保持する。

低周波統計に候補周期を使うなら、statistic/window/settling exclusion/PWM phase/aliasing/許容bias・variance・false-positive/false-negative/expanded uncertaintyを事前定義。25/75ms timestampsを等間隔化・補間・uniform 20Hzと再ラベルしない。校正有効なtraceable referenceと同時取得し、PWM0..30、閾値近傍、channel-switch直後/settled、温度/電源条件を含める。合格は事前承認したuncertainty budget内、bias/variance/誤分類/repeatability限界内、timing/settling条件内。限界数値は要求判定分解能から試験前に承認する。未測定精度は保証しない。未指定・未測定はBLOCKED。

## E. fsync・保存性能

TX intentの完全frame bytes、command/session/epoch/context、host monotonic timestampをappendし、file fsync成功（新規file/rename/manifest更新時は必要なdirectory fsync含む）を確認する前にnonzero PWMをserialへ渡さない。intent fsync failure/exception/timeout/unknownではnonzero送信禁止。serial pathが使えるならSTOP best-effort。ただしSTOP intent永続化も失敗なら送信結果/証跡unknown、package incomplete。RX ACK/sample/STOP responseはraw byte rangeと受信時刻を先にEvidenceへappend/fsync。durableでないACKはstage進行根拠にしない。Evidence writer failure後はnonzero PWM禁止、可能ならSTOP。fsyncがstage/ACK deadlineを超えたら遡及stage時刻を作らず、次stageへ進まず、STOP attempt・aborted/incomplete。crash/restart後はdurable intent/ACK/RX byte range/checkpoint/manifest hashを照合。send outcome unknownなintentは再送しない。

固定ms閾値は設定しない。target PC/OS/kernel/filesystem/mount/storage/controller、電源mode、空き容量、background load、Evidence record size/rate、RawLog concurrent writeを固定したbenchmark profileでintent/RX/ACK/file append/file creation/directory fsync/manifest finalize別に測定する。count、mean、median/p50、p95、p99、p99.9、max、timeout/error、durability/restore errorを記録。合格式は各critical pathで measured worst-case persistence latency + serial/ACK/scheduler worst-case latency + preapproved safety margin < applicable command/stage deadline、かつp99/p99.9もdeadline内。母数・測定期間・margin・deadlinesは実行環境条件として試験前に承認する。fsync failure/crash recovery T17/T10も合格必須。未測定数値は記載しない。

## F. 最終区分

決定済み: ATmega328P reference baseline、EEPROM/SRAM容量、wear arithmetic、16MHz VCC≥4.5V、4.3V BOD単独不十分、external supervisor/hold-up要件、commit order/fail-closed、SRAM上限、STOP action order/TX独立、ADC channel roles/nonuniform cadence、fsync intent-before-send/fail-closed。

条件付き決定: EEPROM journalは実chip確認とsupervisor/hold-up適合時のみ。満たさなければEEPROM-only採用禁止。ADC statisticは事前基準のreference比較合格時のみ。fsync性能はtarget benchmark profileとdeadline承認後に数値合否判定。

実機/実装確認: chip marking/signature、fuse readback、VCC/reset/hold-up waveform、EEPROM interruption、compiler map/sizeof/stack、STOP pin/driver enable、ACS712 exact variant/filter/reference accuracy、storage p99.9/max/crash recovery。いずれも本作業では未実施。
