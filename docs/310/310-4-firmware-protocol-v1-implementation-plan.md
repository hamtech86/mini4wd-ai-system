# 310-4 Firmware Protocol V1 implementation work package

Status: **implementation required; not hardware-qualified**

Base design: 310-4 v0.5, PR #183 HEAD `b9c7f1713c4566c3fc267f6da7c4bfc30cd25ccb`.

Firmware baseline inspected: `firmware/motor/MotoreRev.ino` on `main` and PR #183 HEAD.

## 1. Confirmed baseline gap

The current firmware implements a legacy newline-delimited ASCII command protocol:
- `STOP` and `STOP#<nonce>` call `stopMotor()`, invalidate `driveArmed`, clear `activeArmToken`, and emit text responses.
- `ARM=<8 hex chars>` arms the legacy token gate and emits `ARMED,<token>`.
- Tagged legacy `PWM=<n>@<token>` commands set PWM and emit `OK`.
- `stopMotor()` writes PWM zero and both direction pins LOW, and clears runtime running/paused state.

It does **not** implement the normative v0.5 binary wire protocol:
- Magic `0x344D`, protocol version `0x01`, 17-byte header, CRC-16/CCITT-FALSE, COBS framing.
- `HELLO/HELLO_ACK` with fresh nonce echo and committed uint64 boot identity.
- `ARM/ARM_ACK`, `PWM_SET/APPLY_ACK` with session/epoch/command/context identity.
- Binary `STOP_REQ/STOP_ACK`, stale-session acceptance and four-entry STOP replay/conflict history.
- `STATUS/ERROR/ADC_BATCH` binary frames.
- EEPROM 16-slot boot-generation journal and fail-closed `BOOT_ID_INVALID` behavior.

Therefore the host ProtocolV1Session implementation is not interoperable with this firmware. The legacy ASCII STOP handler is not a substitute for binary STOP_REQ. No compatibility or safety claim may be inferred from the existing text commands.

## 2. Normative implementation order

### FW-01 — bounded binary frame codec
- Implement COBS stream framing, exact frame length checks, CRC-16/CCITT-FALSE, magic/version/flags/type validation.
- Maximum wire workspace is 194 bytes including delimiter. One RX workspace and one TX workspace only; no dynamic allocation, String, recursion, VLA, or unbounded queues.
- Parser must recover at a delimiter after malformed/oversize frames without corrupting subsequent valid frames.
- Add native host-side C++ tests with golden frames shared against `measurement_310/protocol_v1.py`.

### FW-02 — boot identity journal
- Implement the exact 16×16-byte EEPROM journal at addresses 0–255 and provisioning record at 256–259.
- Never auto-provision or repair corrupt identity. Commit generation+1 before HELLO or ARM is available.
- Power-cut injection tests must cover every write/readback boundary; invalid identity must keep PWM disabled and reject ARM/nonzero PWM.

### FW-03 — state machine and command identity
- Implement HELLO nonce/session binding; ARM success only with committed boot identity, exact session/epoch, fresh command ID and nonzero context token, with initial PWM zero.
- Implement PWM_SET exact identity checks and APPLY_ACK echo. Check STOP latch immediately before applying output; discard any queued/stale PWM.
- Implement duplicate command semantics and command-ID freshness exactly as v0.5.

### FW-04 — STOP path
- On syntactically valid and CRC-valid STOP_REQ, process STOP irrespective of stale session/epoch.
- Set STOP latch first; invalidate ARM and queued PWM; PWM=0; both direction pins LOW. STOP action must not wait for TX drain, ACK, ADC completion, or storage.
- Implement exactly four retained STOP history entries per boot epoch and the v0.5 relation/outcome/state enums.
- STOP_ACK is best-effort and follows the safety action. Software STOPPED must never be represented as physical standstill/current-zero proof.
- Fault-injection tests must demonstrate STOP preempts a queued PWM_SET and duplicate/conflicting/full-history cases match v0.5.

### FW-05 — ADC and telemetry
- Preserve A0/A1/A2/A3/A4/A5 roles from v0.5; A0/A1 must not be averaged or substituted.
- Implement 12-sample ADC_BATCH, per-sample timestamps, sequence, status, token and batch loss snapshot exactly as the normative 173-byte payload.
- Validate channel schedule, dummy conversion, ADC acquisition bounds, buffer ownership, loss accounting and no overwrite while TX owns the workspace.
- Cross-check golden payloads with Python codec.

### FW-06 — SRAM, stack, build and static verification
- Compile against pinned Arduino AVR core/compiler and actual board profile.
- Prove `.data + .bss <= 900B`, worst-case stack <=700B, untouched reserve >=448B; include UART rings and all buffers.
- Verify RX/TX workspace 194B each, no additional 173B staging buffer, heap use zero in critical paths.
- Capture linker map, `sizeof` inventory, stack watermark/canary evidence, compiler/toolchain versions and binary hash.
- Resolve BOD/16MHz power integrity separately; software compile cannot qualify clock/power safety.

## 3. Host compatibility acceptance

A hardware-free protocol integration harness must execute:
1. HELLO with exact nonce echo and committed boot identity.
2. ARM with token echo and no PWM change.
3. 31 sequential PWM_SET/APPLY_ACK exchanges with exact command/session/epoch/context identity.
4. STOP_REQ with current, stale and absent session; STOP action precedes STOP_ACK.
5. Duplicate same STOP identity, same ID/different reason conflict, and history-full behavior.
6. STOP racing with queued nonzero PWM; no post-latch nonzero output.
7. malformed COBS, bad CRC, unsupported version/type, truncated and oversized frames.
8. reboot/EEPROM journal interruption and identity corruption cases.
9. ADC_BATCH golden frame decode and 12 sample records.
10. SRAM/stack/build evidence captured from the exact source commit.

No host-only test can qualify physical driver cutoff, motor current decay, FET failure, MCU brownout behavior, or independent STOP hardware.

## 4. Safety and release gates

- This work package is software implementation only. No Arduino upload, serial connection to `/dev/ttyUSB0`, motor energization, or hardware test is authorized by this document.
- Keep PRs Draft until FW-01..FW-06 and host compatibility acceptance are complete and reviewed.
- Do not merge firmware into the hardware baseline or claim 310-5 acceptance based on CI alone.
- T09/T15 require separately authorized STOP path/driver/physical cutoff qualification. T18 requires an approved target-host/storage profile and STOP reserve/margin. Neither is satisfied by firmware host tests.
- `HARDWARE_CURRENT_LIMIT_CONFIRMED=false` remains the current gate.

## 5. Audit result (2026-11-05)

The firmware gap was verified against both `main` and PR #183 HEAD. The host-side normal-completion STOP regression is green (Actions #1408, 528 passed), but that only verifies host code. Firmware protocol implementation is a separate blocking workstream and has not started in this work package.
