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
