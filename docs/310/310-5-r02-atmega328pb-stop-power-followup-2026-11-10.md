# 310-5 R02 — ATmega328PB, STOP path, and power/reset follow-up

Date: 2026-11-10  
Scope: source review, host CI, and compile-only target build. This document is a risk/evidence update, not a 310-5 acceptance, hardware authorization, or specification change.

## 1. Exact target build and resource evidence

PR #194 adds a pinned compile-only profile. The successful exact-head run is:

- PR: https://github.com/hamtech86/mini4wd-ai-system/pull/194
- Workflow run: https://github.com/hamtech86/mini4wd-ai-system/actions/runs/42815131086
- Workflow head: `f35c51e7b0d4b51ea7e27267596b33db04a89fc7`
- Checked-out source SHA in the preceding full artifact run: `9bc327677f910dc4210a55c446c4636e7547b059`; the subsequent run re-ran the same target compile and asserted the expanded build properties.
- MiniCore: `3.1.3`
- FQBN: `MiniCore:avr:328:variant=modelPB,clock=16MHz_external`
- Expanded properties asserted by CI: `build.mcu=atmega328pb`, `build.f_cpu=16000000L`, `build.variant=pb-variant`.

Legacy `MotoreRev`, independent `MotoreRevV2`, and `ProvisionBootIdentity` compile successfully for the selected target. Compilation did not upload firmware, connect to a device, write EEPROM, or alter fuses.

Protocol-v2 resource result:

| Requirement | Result | Disposition |
|---|---:|---|
| `.data` | 146 B | measured in target build |
| `.bss` | 747 B | measured in target build |
| `.data + .bss` | 893 B / 900 B | PASS, 7 B margin |
| Conservative stack bound | 294 B / 700 B | PASS, static call-chain estimate |
| Remaining SRAM after bound | 861 B / 448 B minimum | PASS |
| RX workspace | 194 B | PASS |
| TX workspace | 194 B | PASS |

The 294 B stack bound includes the observed deepest command-cache call chain, AVR return addresses, UART0 TX ISR frame/helper, and interrupt PC. It is static compiler/disassembly evidence, not a physical stack-watermark measurement. The result is specific to this pinned target build and must be regenerated after source, compiler, core, flags, or clock changes.

The BOD fuse is explicitly not configured by this compile workflow. No actual MCU signature, oscillator, fuse, or installed firmware state is established by CI.

## 2. ATmega328PB 16 MHz supply requirement

Microchip's ATmega328PB datasheet specifies the 20 MHz speed grade only at VCC = 4.5–5.5 V; 16 MHz operation therefore requires VCC to remain within the corresponding 4.5 V minimum operating range. The on-chip 4.3 V BOD selection cannot, by itself, guarantee reset before the supply falls below the 16 MHz operating minimum. The datasheet also describes BOD threshold hysteresis and its detection-time condition.

Reference: https://ww1.microchip.com/downloads/aemDocuments/documents/MCU08/ProductDocuments/DataSheets/40001906C.pdf

Disposition:
- ATmega328PB / 16 MHz build configuration: SOFTWARE BUILD PASS.
- Actual clock source/frequency and board identity: NOT RUN.
- Actual BOD fuse setting and threshold on the installed MCU: NOT RUN.
- Actual MCU VCC minimum during operation/transients: NOT MEASURED.
- Whether an external voltage supervisor is needed: BLOCKED pending the actual VCC/BOD assessment.
- If an external monitor is used, its part, threshold tolerance, hysteresis, reset connection, and physical trip/release behavior: NOT CONFIRMED / NOT RUN.

A 4.3 V BOD selection alone cannot guarantee that a 16 MHz ATmega328PB remains within its 4.5 V minimum operating range. The current power-drop strategy must be assessed against the actual MCU VCC rail and the installed fuse configuration. Issue #35 classifies an external supervisor as an INVESTIGATE item rather than a universal blanket requirement. If the chosen design uses an external monitor, a document-only claim is insufficient: its actual threshold and reset behavior must be physically verified before PASS. No fuse operation or live test is authorized here.

## 3. Reset-time output state

The firmware's `UnoOutputAdapter.safe_outputs()` writes PWM and direction latches LOW, configures the pins as outputs, then writes PWM=0 and direction LOW. This is a source-level startup action only; the adapter explicitly has no physical feedback.

The ATmega328PB datasheet states that I/O ports are tri-stated during reset. Consequently, the later `setup()` writes do not establish the electrical state from reset assertion until the firmware reaches `safe_outputs()`.

Required unresolved hardware evidence:
- default pull-down / inhibit behavior for L298N enable/PWM and direction inputs during reset, brownout, and unpowered MCU conditions;
- whether the driver can produce output while MCU pins are high-impedance;
- the actual external voltage-monitor/reset path and recovery timing;
- physical no-auto-resume behavior after supply collapse and recovery.

All are NOT RUN / BLOCKED. No reset or brownout test is authorized by this document.

## 4. STOP path — software candidate versus installed wiring

### Source-level behavior

- `ProtocolV2Device::handle()` dispatches STOP before ARM/PWM command handling.
- `handle_stop()` calls `outputs_safe()` first, clears active PWM/token, sets the stopped/fault-stopped state, and records STOP history afterward.
- ARM is accepted only from `DEVICE_IDLE`; STOP is terminal for the current session. This is a source-level no-same-session-restart property.
- `SequenceController.abort()` takes a non-blocking abort lock, attempts STOP before RawLog append/fsync, and preserves incomplete work if later logging fails.
- The v2 host session uses a dedicated independent STOP writer with a bounded caller wait. Command transport write/flush has a separate timeout and becomes fail-closed with UNKNOWN outcome after a timeout. The normal command timestamp is captured after write/flush completion.
- The firmware services the single `Serial` RX stream in bounded 24-byte foreground batches before its TX scheduler. This avoids waiting for the TX queue to drain before processing already-received STOP bytes, but does not make a STOP frame jump ahead of earlier bytes already queued on that same UART.

### Known endpoint mapping gap

The real v2 host-session factory currently refuses a real serial configuration unless a dedicated STOP writer endpoint is supplied and is physically distinct from the command port. The known device mapping is:
- motor command MCU: `/dev/ttyACM0`;
- battery-discharge controller: `/dev/ttyUSB0`.

The battery-discharge port is not an available motor STOP endpoint and must not be repurposed. No third dedicated safety-controller/STOP endpoint or wiring path is identified in the current motor circuit description. The firmware's reviewed RX path is the single `Serial` input; a second host pathname alone does not create an independent electrical route to that input or to the L298N enable path.

Issue #35's 2026-11-09 risk decision classifies an independent STOP circuit / independent driver cutoff as **INVESTIGATE**, not a universal blanket requirement. The binding requirement in this assignment is the outcome: STOP must not be blocked by the normal command queue, writer lock, fsync, or a full TX wait. The current implementation's dedicated-endpoint strategy is not mapped to the known hardware, so its real-hardware STOP path is BLOCKED. An alternative software/transport design may be evaluated, but it must demonstrate bounded STOP delivery without byte interleaving, unsafe partial-frame handling, or reliance on the normal durability/TX path. If a separate hardware inhibit is proposed, assess its risk reduction and cost under Issue #35 rather than assuming it is automatically mandatory.

Therefore:
- host-side STOP scheduling/timeout design: SOFTWARE CANDIDATE PASS;
- current dedicated STOP endpoint mapped to actual motor hardware: BLOCKED;
- STOP bypass of physical command queue / writer lock / fsync / TX wait: NOT QUALIFIED on the installed circuit;
- physical PWM=0, direction LOW, ARM invalid after STOP: NOT RUN;
- physical STOP latency and no-auto-resume: NOT RUN.

Do not claim that a test using two pseudo-terminals proves the actual motor hardware has two independent control paths.

## 5. Main power switch and no-auto-resume boundary

The previously shared circuit description places the physical main switch in the L298N motor-driver supply path, while the Arduino remains powered from PC USB. Turning that switch OFF therefore does not itself reset the MCU or set the firmware STOP latch. If the MCU continues running with PWM/direction outputs asserted while the L298N supply is removed, restoring driver power could re-enable the prior output unless a separate hardware inhibit or an explicit MCU STOP has made the output safe.

This is a topology-based risk, not a claim that a live test was performed. Operator confirmation that the motor supply is OFF and the rotor is stopped is not equivalent to an independent MCU STOP latch or proof that the enable path remains inhibited on power restoration.

Issue #35 permits operator main-switch mitigation only when the switch is accessible and the residual risk is explicitly assessed; the switch is not equivalent to an MCU STOP latch. A separate hardware interlock is an investigation option, not an automatic requirement. The actual default-disabled behavior and recovery risk must be established before PASS. Any wiring change requires upper approval. No hardware modification or test is authorized here.

## 6. A0–A5 and loss accounting

The independent v2 acquisition path remains statically separated:
- A0 = winding-current ADC sample;
- A1 = brush-stability observation, not converted to a substitute current;
- A2/A3 = reference/raw-only channels;
- A4/A5 = independent voltage samples.

The v2 host loss accumulator defines six independent channel counters. For each complete attributable 1,000,000 µs half-open window, each channel has 20 expected slots; statuses 0 count attempted+valid, statuses 1/2 count attempted+invalid, status 3 counts not-acquired, and `missing = expected - attempted`. Incomplete or sequence-gap-affected windows are `UNATTRIBUTABLE`, with missing left null rather than guessed. This is source-level/host-test evidence, not physical sampling qualification.

The legacy ASCII `MotoreRev.ino` / DATA26 path still contains the A0/A1 average and downstream legacy-derived metrics. It remains FAIL and must not be represented as the 310 v2 measurement path. The independent v2 path's static channel separation does not erase this legacy-path finding. No RawLog v1 historical rewrite or automatic v1-to-v2 migration is authorized.

## 7. Device epoch checkpoint correction and regression

The earlier R01 statement that a same-boot host restart had no timestamp checkpoint is superseded by the current source:
- `load_latest_device_clock_checkpoint()` reads valid RawLog v2 ADC_SAMPLE records for the same verified boot epoch;
- the host restores the device clock from the latest durable sequence/timestamp/elapsed triple;
- missing sequence slots are kept unattributable;
- the partially observed 1-second window spanning process restart is marked UNATTRIBUTABLE rather than fabricated as complete.

The batch high-water regression assertion was corrected in PR #195 (test-only). Exact-head CI run:
https://github.com/hamtech86/mini4wd-ai-system/actions/runs/42814162228

Result: 649 passed, 2 xfailed. The test correction does not change production code or measurement data.

## 8. Target-host persistence budget

The GitHub-hosted T18 production-path profile is software evidence on the runner's filesystem. It is not the user's target PC and cannot establish that PC's filesystem/fsync latency distribution. The required target-host save-stage 10-second budget, including measured maximum and p99.9, remains NOT RUN until the approved target-host diagnostic is performed. No target-host or hardware action is authorized by this report.

## 9. Current disposition

| Requirement | State |
|---|---|
| ATmega328PB 16 MHz compile target | PASS — CI properties asserted |
| Protocol-v2 SRAM / static stack budget | PASS — static build audit |
| v2 A0/A1 separation | PASS — source-level only |
| legacy DATA26 A0/A1 average path | RETIRED / DISABLED BY DEFAULT — archived source remains noncompliant |
| per-channel 1-second loss accounting | PASS — source/host-test candidate |
| same-boot timestamp checkpoint | IMPLEMENTED — host regression pass |
| command_sent_ns after serial write/flush | PASS — source review |
| fsync uncertainty blocks further ARM/nonzero commands | SOFTWARE CANDIDATE; physical/target-host qualification pending |
| STOP host ordering / non-blocking abort entry | SOFTWARE CANDIDATE PASS |
| independent STOP endpoint on actual hardware | BLOCKED |
| reset/brownout electrical output state | NOT RUN / BLOCKED |
| external monitor threshold and physical behavior | NOT RUN / BLOCKED |
| target-host save-stage max and p99.9 | NOT RUN |
| current limit / thermal / wiring qualification | BLOCKED / NOT RUN |
| 310-5 formal acceptance | NOT ACCEPTED |
| 310-6 | BLOCKED |

`HARDWARE_CURRENT_LIMIT_CONFIRMED=false` remains unchanged. The 12 V DC adapter clarification is retained; its unverified current-limit and simultaneous voltage/current performance are not made a prerequisite for unrelated software work, and are not treated as proof of electrical safety.

No Arduino connection, `/dev/ttyACM0` or `/dev/ttyUSB0` access, firmware upload, fuse/EEPROM operation, motor energization, or 310-second measurement was performed or authorized.


## 10. Latest exact-head hosted T18 production-path profile

The R02 documentation commit triggered the existing PR #193 T18 workflow on exact head `ef52bff97e0068f6c92acd9db7cf526cecd1490c`.

- Run: https://github.com/hamtech86/mini4wd-ai-system/actions/runs/42815620391
- Result: PASS.
- 31 PWM stages; 3,100 ADC batches; 37,200 ADC slots / ADC_SAMPLE records.
- 310 one-second loss-window summaries; all PASS.
- RawLog validation errors: 0.
- Evidence events: 10,143; Evidence bundle verified.
- Stage elapsed distribution: p50 134.993 ms; p95 440.584 ms; p99/p99.9/max 1,138.249 ms.
- Final `sequence_complete` phase: one observation, max 1,019.032 ms. Its p99.9 is numerically the same one observation and is not a statistically meaningful percentile. RawLog finalization max for that final stage: 830.447 ms.
- Profile JSON SHA-256: `a4b4890165b9a1eeaa82621d2071243490fa438716e8bff0716255b4dbab7147`.

Evidence boundary: GitHub runner Ubuntu 26.04 / ext4, in-memory protocol-v2 peer, real host-side RawLog/intent/Evidence files and production fsync calls. No serial device was opened and no physical hardware was used. The profile marks stage timing as observational only. It does not satisfy the target Linux Mint host's 10-second save-stage qualification or its required max/p99.9 distribution. Target-host diagnostic remains NOT RUN.


## 11. Legacy DATA26 retirement and latest exact-head verification

The legacy DATA26 sketch has now been isolated from the current 310 build:
- Commit `224074c625b7cb146f4ffc1f7c7ea7e767015934` adds a compile-time guard to `firmware/motor/MotoreRev.ino`; a normal build fails unless the explicit archival-only macro `M4WD_ENABLE_LEGACY_DATA26` is supplied.
- `firmware/motor/README.md` identifies `MotoreRevV2` as the only current 310 firmware and the DATA26 sketch as historical-only.
- `arduino-firmware-compile.yml` now builds the Protocol V2 sketch and Boot Identity Provisioner for ATmega328PB / 16 MHz; it no longer builds the legacy sketch for Arduino Uno.
- `motor-firmware-compile.yml` verifies the default-build guard, verifies that the V2 source has no A0/A1 averaging path, and runs the legacy safety harness only with explicit archival opt-in.
- The Python native safety test first proves that compiling the legacy sketch without the opt-in macro is rejected, then runs the legacy harness with explicit opt-in.

Latest exact PR #193 head: `7d53858db2f7b07a1f1b5d6d17036fa13a4ff089`.

Exact-head verification:
- Legacy retirement guard/native safety workflow: https://github.com/hamtech86/mini4wd-ai-system/actions/runs/42816321247 — PASS.
- ATmega328PB current firmware compile: https://github.com/hamtech86/mini4wd-ai-system/actions/runs/42816321351 — PASS.
- Full regression: https://github.com/hamtech86/mini4wd-ai-system/actions/runs/42816321481 — PASS, 649 passed / 2 xfailed.
- T18 production-path profile: https://github.com/hamtech86/mini4wd-ai-system/actions/runs/42816321395 — PASS.

Latest T18 profile:
- 31 PWM stages; 3,100 ADC batches; 37,200 ADC slots.
- 310 one-second loss windows; all PASS; RawLog validation errors 0; Evidence events 10,143; bundle verified.
- Stage elapsed p50 180.718 ms; p95 217.563 ms; p99/p99.9/max 1,480.460 ms.
- Final `sequence_complete` phase has one observation at 1,311.032 ms; RawLog finalization for that stage is 1,014.529 ms. A one-observation p99.9 is not statistically meaningful.
- Profile JSON SHA-256: `d16ad4c22378851b0bdb8f5308a0302e04a61c333be4d80c8f8ec4dbe708e4c6`.

The T18 run used a GitHub-hosted Ubuntu 24.04 runner with ext4 and an in-memory protocol-v2 peer. It is not the target Linux Mint host and does not qualify the target-host 10-second save-stage max/p99.9 distribution. Target-host diagnostic remains NOT RUN.

The legacy source is preserved for historical compatibility only; the current 310 build does not compile or use it. This does not rewrite historical RawLog v1 files or add any v1-to-v2 migration.


## 12. Protocol v2 sample-slot size clarification

The earlier source-audit concern about the v0.5 14-byte sample representation versus the Protocol v2 12-slot batch representation is withdrawn. The 2026-11-05 protocol v2 amendment recorded in PR #183 explicitly assigns a full-width first sample sequence in the ADC_BATCH header and 12 implicit contiguous sample slots. PR #188's protocol-v2 implementation and the current v2 firmware use that amended batch contract. The 12-slot representation is therefore an intentional protocol-v2 amendment, not an unresolved 14-byte/12-byte implementation mismatch. The amendment does not waive the requirement that Issue #35 remains the normative authority.


---

## 13. 2026-11-10 PR #193 exact-head artifact audit

### PR #193 hosted verification at head 018cd69

The PR #193 workflows below completed successfully on head `018cd69ec7a1eb5138de514100e741a236ca55e5`. The code-bearing commit is `7d53858db2f7b07a1f1b5d6d17036fa13a4ff089`; the intervening commit is documentation-only.

- Full regression run `42817063013`: PASS, 649 passed / 2 xfailed.
- T18 production-path run `42817062897`: PASS.
- ATmega328PB compile run `42817062970`: PASS.
- Legacy DATA26 retirement/native safety run `42817063175`: PASS.

T18 artifact:
- Artifact ID: `13765556426`
- Artifact ZIP SHA-256: `cf4d47373f9e309dff01a8c1823b734c15bc2c5ff8c990c108823e62870f8354`
- Profile JSON SHA-256: `39b4f2bae978ff62d02f4d1e6de0dee08a9de6368b7071d95c8d306aa840ebe3`
- 31 PWM stages; 3,100 ADC_BATCH; 37,200 ADC_SAMPLE; 310 loss-window summaries, all PASS.
- Evidence events: 10,143; Evidence bundle verified; RawLog validation errors: 0; normal-completion STOP_REQ: 1.
- Stage elapsed p50 196.871 ms; p95 658.370 ms; p99/p99.9/max 1,638.843 ms. These are observational only.
- Runner: Linux 7.0.0-1019-azure, Python 3.10.22; in-memory Protocol V2 peer; production RawLog/intent/Evidence files and fsync. No physical device or serial port was opened.

Independent RawLog artifact inspection:
- 6,200 ADC_SAMPLE records each for A0, A1, A2, A3, A4 and A5.
- Roles are respectively `winding_current`, `brush_stability_observation`, `magnetic_reference`, `thermistor_reference`, `voltage_v4`, and `voltage_v5`.
- A1 has no `converted_value` or `converted_unit`.
- The 37,200 device sample sequence values are contiguous from 0 through 37,199; available `device_elapsed_us` values are monotonic from 0 through 309,991,666.
- Evidence sidecar SHA-256 matches its bundle manifest; the intent journal contains 93 records.

This validates the hosted production-path artifact and channel separation. It is not a target Linux Mint host result, physical ADC accuracy proof, or hardware qualification.

### SRAM audit artifact cross-reference

The dedicated PR #194 audit run `42816586095` produced artifact ID `13765675712` (ZIP SHA-256 `f2d526df9c1da539f9fb9dae40137bb5b806c6b75240e169594c430fdbda6267`). Its checked-out commit is `fe41e491ae292d93dc87765e6a163f9da0284c29`.

The following six firmware source-file blob SHAs were independently compared between PR #193's current branch and PR #194's audit branch and were identical:
- `MotoreRevV2.ino`: `39bfc97adadd6467280f88ea5603f5bc0f5dcf76`
- `ProtocolV2Codec.h`: `73a00077f8c9594c500e7fc9532a5e001c740c6f`
- `BootIdentityJournal.h`: `4dca7dc6cc41a61bfa2cc3fc77be5a93d1ab78f4`
- `ProtocolV2Device.h`: `41f7d69114232f4a8794de405dfc84199033cce6`
- `ProtocolV2TxScheduler.h`: `fdf1d244f8f0f0c374a8a621558c863900a8fdcb`
- `ProtocolV2AdcScheduler.h`: `4204fb673b92b1680eb395f9d82ea9cd68f905ca`

The audited build used MiniCore 3.1.3, `MiniCore:avr:328:variant=modelPB,clock=16MHz_external`, and compile-only settings. Its retained stack report states:
- `.data=146 B`, `.bss=747 B`, total `893 B`.
- Conservative stack bound `294 B`.
- Remaining SRAM after the bound `861 B`.
- RX workspace `194 B`, TX workspace `194 B`.
- The disassembly confirms the audited `__vector_19` ISR calls `HardwareSerial::_tx_udr_empty_irq()`; the stack report includes both frames.

This is source-equivalent evidence for the current PR #193 firmware because the six firmware blobs match exactly. It is not an exact-PR-HEAD audit run: PR #194 remains a separate Draft/Open branch based on an earlier PR #193 commit. No upload, fuse change, EEPROM write or hardware connection occurred.

### Remaining qualification boundary

The exact-head hosted evidence does not close:
- Target Linux Mint T18 diagnostic and its actual max/p99.9 filesystem timing.
- Physical reset/BOD output state and no-auto-resume.
- STOP behavior on the installed wiring; the independent STOP endpoint is not mapped.
- Current limit, supply/wiring/protection and thermal qualification.

The target-host T18 profile is KEEP as a diagnostic, not an 8,000 ms acceptance gate. Physical current-limit/power/wiring/thermal safety remains KEEP and highest priority. `HARDWARE_CURRENT_LIMIT_CONFIRMED=false`; 310-5 remains NOT ACCEPTED and 310-6 remains BLOCKED.
