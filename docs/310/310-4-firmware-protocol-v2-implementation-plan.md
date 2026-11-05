# 310-4 Firmware Protocol v2 implementation plan

Status: implementation branch created; firmware implementation and qualification are not complete.
Normative design: docs/310/310-4-design-v0.5.md, amendment "310 protocol v2 amendment — 2026-11-05", commit 704b579f8f07d908d83213945e760b2f485c70c0.

## 1. Baseline and incompatibility

The existing firmware/motor/MotoreRev.ino is legacy newline-delimited ASCII firmware. It does not implement either binary protocol v1 or v2. The v2 host codec/session now exist on the 310-5 candidate branch, but no v2 firmware build exists yet.

Protocol v2 replaces the 17-byte v1 header with a 29-byte header containing the complete UUID session identity. HELLO_ACK returns the full boot identity and current device-owned uint64 next sample sequence. ADC_BATCH uses a uint64 first sequence and 12 implicit contiguous sample sequence values. Maximum ADC_BATCH wire length is 188 bytes.

## 2. Firmware implementation order

### FW2-01 — bounded COBS/CRC frame codec
- Add a fixed-memory, Arduino-independent C++11 codec suitable for native host testing and AVR compilation.
- Exact constants: magic 0x344D, protocol version 0x02, header 29B, CRC-16/CCITT-FALSE, COBS + zero delimiter.
- Validate exact message payload lengths, flags, UUID zero/nonzero rules, command ID rules, epoch tag and all payload enums/ranges.
- Maximum wire buffer 194B; no heap, String, recursion, VLA, or unbounded queue.
- Add native golden-vector tests for every message type, malformed COBS, CRC, truncated/oversized frames, and recovery at the next delimiter.

### FW2-02 — EEPROM boot identity
- Implement the adopted 16-slot × 16-byte journal and provisioning record from the 310-4 specification.
- Commit a new boot_id64 before accepting HELLO or enabling any output.
- No auto-provision, no corrupt-journal repair, no random substitute identity, and no sequence reset if boot identity is invalid.
- Implement deterministic power-cut injection at every EEPROM write/readback boundary in the native model.
- Actual EEPROM interruption/fuse tests remain a separate hardware authorization gate.

### FW2-03 — device-owned sample sequence
- Maintain uint64 next_sample_sequence64 for the current committed boot_id64.
- Increment once for every scheduled ADC attempt, including failed/not-acquired slots.
- Do not reset on HELLO, ARM, STOP, host reconnect, or session UUID change.
- Return current next sequence atomically in HELLO_ACK and STATUS.
- UINT64_MAX exhaustion latches a fault; wrap is prohibited.
- ADC_BATCH starts at first_sample_sequence64 and assigns slot i to first+i.

### FW2-04 — session and command state machine
- Bind the full 16-byte UUID from HELLO to the committed boot_id64.
- Echo full UUID in every response/data frame.
- Fresh host nonce must match exactly; delayed ACK from prior UUID must be rejected.
- ARM requires committed identity, valid state, fresh command_id, and nonzero stage context; ARM always applies PWM=0.
- PWM_SET validates UUID, epoch tag, command freshness, context and state before output action.
- Duplicate command ID + identical payload returns cached ACK; changed payload conflicts; regressions are rejected.

### FW2-05 — STOP priority
- Valid CRC/syntax STOP_REQ latches STOP first, invalidates ARM and pending PWM, sets PWM=0 and both direction pins LOW before any ACK/transmit work.
- STOP action is independent of TX drain, ADC batch completion and storage.
- Implement four-entry STOP history and exact duplicate/conflict/history-full semantics.
- STOP_ACK is best effort; never equate software latch with physical cutoff or rotor standstill.
- Native tests must race STOP with queued PWM and prove no post-latch nonzero output.

### FW2-06 — ADC acquisition and telemetry
- Preserve A0/A1/A2/A3/A4/A5 roles and non-averaging requirements.
- Preserve per-conversion timestamps and channel/context snapshots.
- Every scheduled attempt consumes a uint64 sequence slot.
- 12 sample slots per complete batch; no partial batch; dropped batch must leave a visible sequence gap/loss counter.
- RX/TX workspace ownership and 194B maximum remain enforced.

### FW2-07 — AVR build/resource proof
- Pin Arduino AVR core/compiler and board profile.
- Produce .elf, .hex, linker map, compiler/toolchain versions, and SHA-256.
- Prove .data + .bss <= 900B, worst-case stack <=700B, reserve >=448B, RX/TX workspace <=194B each, no extra 173B staging buffer, no heap in critical paths.
- Inspect actual UART ring allocations and worst nested ISR/call stack.
- No claim of BOD, EEPROM power-fail, ADC accuracy or physical STOP qualification from compilation.

## 3. Host/firmware interoperability acceptance

The host-side acceptance harness must exercise:
1. HELLO/HELLO_ACK full UUID, nonce, boot_id64 and next_sample_sequence64.
2. ARM/ARM_ACK with PWM held at zero.
3. 31 PWM_SET/APPLY_ACK exchanges with exact UUID/epoch/command/context.
4. STOP from current, stale and absent session.
5. STOP duplicate, conflict, history full, and STOP racing queued PWM.
6. Old-session frame rejection, including identical command_id and boot epoch.
7. ADC_BATCH golden payload and uint64 sequence continuity across uint16 boundaries.
8. Same-boot host restart, stale checkpoint, host backup rollback and explicit gap accounting.
9. EEPROM boot journal corruption, torn write and power-cut model.
10. C++/Python golden vectors and AVR resource proof.

## 4. Release boundaries

- No firmware upload, physical serial connection, motor energization, fuse/EEPROM operation, power interruption, 310-second measurement, or hardware test is included.
- HARDWARE_CURRENT_LIMIT_CONFIRMED=false remains in force.
- Keep this branch unmerged until FW2-01..FW2-07 and host/firmware interoperability tests pass.
- A successful native test or AVR compile is not hardware qualification and does not by itself complete 310-5.


## 5. 2026-11-05 implementation status

- FW2-01: fixed-memory codec header added at firmware/motor/ProtocolV2Codec.h. Native C++11 test covers CRC-16 vector, HELLO full-UUID round trip, ADC_BATCH sequence decoding and 188-byte wire ceiling, zero UUID rejection, and uint64 exhaustion boundary.
- FW2-02: BootIdentityJournal.h added with exact slot/provisioning bytes, marker-last writes, readback, unique highest generation, factory-empty predicate, fail-closed corruption and generation exhaustion.
- Native fault-injection tests cover all 17 writes in a generation commit, both fail-before-write and write-then-report-failure semantics. This includes an ambiguous final marker write: if marker committed despite a failed return, restart discovers that generation and increments again rather than reusing it.
- Native CI run #11 at exact HEAD 38f0331bf5ee19c60d2db5ee1fb9d7b13966d779 completed successfully. The C++11 codec and EEPROM journal model compiled with -Wall -Wextra -Werror -pedantic and both native executables exited successfully.
- Initial runs #7–#10 failed because the test fixture calculated the provisioning CRC from address 0 instead of address 256. The fixture was corrected; run #11 is the first passing evidence for both native targets.
- Arduino Uno compile run #86 is pending at this report update. It currently targets the legacy MotoreRev.ino; the new v2 headers are not yet integrated into that sketch.
- FW2-03 through FW2-07 remain not implemented. No full v2 firmware state machine, STOP preemption, ADC scheduler integration, AVR resource proof for the v2 build, or physical qualification is claimed.


## 6. 2026-11-05 firmware state-machine increment

Added `firmware/motor/ProtocolV2Device.h` and `tests/native/test_protocol_v2_device.cpp`.

Implemented software contracts:
- Boot identity is a constructor/initialization gate. A zero or invalid boot identity cannot complete HELLO or enter an ARM-capable state.
- Startup requests safe outputs before frame handling.
- HELLO binds the full 16-byte UUID; same-session HELLO retry is idempotent and does not reset command freshness/cache. A different UUID cannot orphan an ARMED/RUNNING output.
- ARM requires the bound UUID, full-boot-derived epoch tag, nonzero context token, initial PWM=0, a fresh command ID, and an eligible state. Successful ARM first requests safe outputs and only then enters ARMED.
- PWM_SET requires current UUID/epoch, increasing command ID, active context token and ARMED/RUNNING state.
- Four-entry command-result cache returns the prior ACK for an exact duplicate; a reused command ID with changed payload is rejected. An evicted/old command ID cannot become fresh because the high-water mark remains.
- STOP_REQ executes the safe-output adapter before history classification or ACK construction, clears active PWM/context, and latches STOPPED or FAULT_STOP. Four-entry STOP history distinguishes new, exact duplicate, ID conflict and history-full outcomes.
- Re-arming after STOP requires a new UUID HELLO and new ARM. Old-session PWM is rejected. A prior fatal output/boot fault remains FAULT_STOP and cannot be cleared by STOP.
- ERROR replies use header command_id=0 and place the related request ID in the ERROR payload, matching the v2 codec's header rules.

Native test coverage:
- HELLO full boot identity/nonce/sequence response.
- ARM with PWM held at zero.
- PWM apply and STOP preemption before a subsequent queued PWM request.
- STOP invalidates context and prevents same-session restart.
- New UUID + HELLO + ARM is required for restart.
- Old-session drive frames cannot alter the new session output.
- Duplicate STOP and same stop_request_id/different reason conflict.
- Invalid boot identity cannot bind a usable session.
- Idempotent HELLO retry does not reset command cache; a new UUID is rejected while a drive output is active.

CI:
- Native protocol v2 workflow run #22, run ID 41963370586, exact HEAD `cec01535717d901552cb99da9b368623379eb59d`: success. Both original codec/journal targets and the new device-state-machine compile/run steps passed.
- Native workflow at subsequent exact HEAD `88b777f7c23577b79e1d2794424bb9d66da40c42`, run ID 41963453353: success. Includes codec, EEPROM journal fault-boundary suite and device safety vectors.
- Additional duplicate-command/active-session regression tests were added at HEAD `a20337655b637ea459e79b39ea734776eacaece9`; native workflow run ID 41963506495 completed success and included the state-machine compile/run steps.

Not yet implemented/qualified:
- No `MotoreRevV2.ino` binary parser/TX scheduler integration.
- No actual Arduino EEPROM adapter or provisioning workflow.
- No direction-selection contract in v2 messages; existing motor direction behavior must be reconciled before enabling nonzero PWM in the sketch.
- No ADC scheduler/cadence adoption or 12-slot batch producer.
- No AVR v2 sketch compile, .elf/.hex/map, SRAM/stack proof.
- No Arduino upload, serial hardware connection, motor energization, EEPROM/fuse operation, physical test, or hardware qualification.


## 7. 2026-11-05 bounded TX scheduler increment

Added `firmware/motor/ProtocolV2TxScheduler.h` and `tests/native/test_protocol_v2_tx_scheduler.cpp`.

- TX uses one 194-byte wire workspace; pending replies are retained as decoded fields only, not a second full-frame buffer.
- A frame remains TX-owned until all bytes are accepted by the serial writer; frame bytes are never interleaved.
- Each service pass writes at most 16 bytes and returns to the caller, allowing the main loop to parse incoming STOP between chunks.
- A pending STOP_ACK supersedes a lower-priority pending reply and is emitted at the next frame boundary. The active frame is not corrupted or interleaved.
- A second lower-priority pending reply is rejected rather than overwriting the pending item or growing a queue.
- This scheduler does not itself perform STOP output actions. The device state machine performs safe_outputs synchronously when STOP_REQ is handled; scheduler only prioritizes the best-effort ACK.
- Native CI for the scheduler increment is running at current code HEAD `74ac55f1f04725f0399c36fef3ae8d5da2765723`; record the exact run conclusion before treating it as verified.

### Direction contract discrepancy — must be resolved before sketch drive integration

The adopted Issue #35 / Issue #172 contract requires explicit FWD/REV direction and records direction with each measurement. The v2 wire contract currently defines ARM as only `stage_context_token + initial_pwm=0` and PWM_SET as only `pwm + stage_context_token`; there is no direction command or direction field. The legacy firmware explicitly drives D7/D8 differently for FWD and REV. Therefore the current v2 device state machine cannot safely select the required direction, and a sketch that silently assumes FWD would not satisfy the authoritative contract.

Before nonzero PWM integration into `MotoreRevV2.ino`, amend v2 so ARM binds a session direction (recommended: add a direction enum to ARM and echo it in ARM_ACK/STATUS), then update host codec/session, test vectors and firmware together. Until that wire-contract amendment is reviewed, do not set either direction pin HIGH and do not claim functional PWM drive integration.

### Current status

FW2-01 codec: implemented; native CI passing.
FW2-02 EEPROM journal: implemented as a native model; native CI passing. Actual Uno EEPROM adapter/provisioning remains open.
FW2-03 sample sequence: core HELLO/STATUS storage fields exist in codec/device object; ADC scheduler and sequence consumption on every scheduled attempt remain open.
FW2-04 command state machine: native implementation/tests added; native CI passing through HEAD `a20337655b637ea459e79b39ea734776eacaece9`.
FW2-05 STOP: synchronous safe-output adapter and native command-state tests added; bounded TX scheduler added; scheduler CI pending at HEAD `74ac55f1f04725f0399c36fef3ae8d5da2765723`. Physical STOP remains unqualified.
FW2-06 ADC: not implemented; 20 Hz remains NOT ADOPTED, so no cadence is invented.
FW2-07 AVR build/resource proof: not started for v2 sketch.
