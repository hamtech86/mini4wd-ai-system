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
- Native workflow run #36 / run ID 41963637848 completed success at exact code HEAD `74ac55f1f04725f0399c36fef3ae8d5da2765723`. All five compile/run steps passed: codec, EEPROM journal, device state machine and bounded TX scheduler.

### Direction contract discrepancy — must be resolved before sketch drive integration

The adopted Issue #35 / Issue #172 contract requires explicit FWD/REV direction and records direction with each measurement. The v2 wire contract currently defines ARM as only `stage_context_token + initial_pwm=0` and PWM_SET as only `pwm + stage_context_token`; there is no direction command or direction field. The legacy firmware explicitly drives D7/D8 differently for FWD and REV. Therefore the current v2 device state machine cannot safely select the required direction, and a sketch that silently assumes FWD would not satisfy the authoritative contract.

Before nonzero PWM integration into `MotoreRevV2.ino`, amend v2 so ARM binds a session direction (recommended: add a direction enum to ARM and echo it in ARM_ACK/STATUS), then update host codec/session, test vectors and firmware together. Until that wire-contract amendment is reviewed, do not set either direction pin HIGH and do not claim functional PWM drive integration.

### Current status

FW2-01 codec: implemented; native CI passing.
FW2-02 EEPROM journal: implemented as a native model; native CI passing. Actual Uno EEPROM adapter/provisioning remains open.
FW2-03 sample sequence: core HELLO/STATUS storage fields exist in codec/device object; ADC scheduler and sequence consumption on every scheduled attempt remain open.
FW2-04 command state machine: native implementation/tests added; native CI passing through HEAD `a20337655b637ea459e79b39ea734776eacaece9`.
FW2-05 STOP: synchronous safe-output adapter and native command-state tests added; bounded TX scheduler added; scheduler native CI passing at exact HEAD `74ac55f1f04725f0399c36fef3ae8d5da2765723`. Physical STOP remains unqualified.
FW2-06 ADC: not implemented; 20 Hz remains NOT ADOPTED, so no cadence is invented.
FW2-07 AVR build/resource proof: not started for v2 sketch.


Exact current branch HEAD `0fb8dbb8c5ea34421dfd31c30b78a7a47ce29bf6` was rechecked by native workflow run #40 / ID 41963694506: success. All codec, EEPROM journal, device state-machine and bounded TX scheduler compile/run steps passed at this exact HEAD.


## 8. Repository CI snapshot (2026-11-05)

Exact code HEAD `0fb8dbb8c5ea34421dfd31c30b78a7a47ce29bf6`:
- Native v2 workflow #40 / 41963694506: success; codec, EEPROM journal, state machine and TX scheduler compile/run passed.
- Break-in and Battery #1446 / 41963694468: all four jobs succeeded; full pytest **259 passed in 9.93s**.
- Arduino Uno compile #100 / 41963694486: success, but it compiles only legacy `MotoreRev.ino`, not a v2 sketch.
- DB Path Safety #580 / 41963694424: success.

The branch later advanced by documentation-only commits to `c0ad824277cb15c376f8bb20173087ee75664d77`; firmware code did not change after the tested code HEAD. These CI results do not establish v2 AVR compilation, SRAM/stack limits, hardware behavior or formal T01–T18 acceptance.


## 9. 2026-11-05 per-stage direction and DISARM increment

The wire and device-state implementation now follows the command-authority amendment in PR #183:

- ARM payload is now 4 bytes: stage_context_token:uint16, initial_pwm=0, direction enum FWD=0 / REV=1. ARM_ACK is 5 bytes and echoes direction; rejected ARM_ACK may use 0xFF (NONE), while successful ACK must echo FWD or REV.
- DISARM (2-byte active context token) and DISARM_ACK (result/state/token, 4 bytes) are separate message types. Successful DISARM calls the synchronous safe-output adapter, clears active context and returns to IDLE while retaining the session UUID, boot epoch, sequence and command high-water.
- Same-session next-stage ARM is allowed only after normal DISARM. STOP remains terminal for the current boot and cannot be cleared by DISARM or a new HELLO; a reset/new boot identity is required before a fresh execution.
- Native device tests cover FWD → DISARM → REV within one session, PWM zero/direction LOW during stage transition, and STOP terminal behavior. Codec vectors cover ARM direction and DISARM wire formats, including NONE sentinel validation.
- The current Output adapter interface now requires set_direction(direction) in addition to safe_outputs() and set_pwm(). No production Arduino adapter or sketch is implemented yet.

Verification status at this document update:
- An initial native run exposed a missing ARM_ACK helper argument; corrected.
- A subsequent native run exposed an outdated STOP test that expected a new HELLO to clear STOP; corrected to assert terminal STOP semantics.
- The next exact-HEAD native run is the acceptance evidence for this increment; do not count the failed runs as passes.
- No v2 sketch, AVR build/map, SRAM/stack proof, physical output test or hardware qualification is claimed.


## 10. 2026-11-05 isolated Uno v2 sketch increment

Added `firmware/motor/MotoreRevV2/MotoreRevV2.ino` as a separate protocol-v2 sketch; the legacy `MotoreRev.ino` remains unchanged.

Implemented in this increment:
- Initializes D5 PWM and D7/D8 direction outputs to non-driving LOW before constructing protocol state.
- Uses a static-storage placement-constructed `ProtocolV2Device`; no heap allocation is used.
- Connects the existing `BootIdentityJournal` to the Uno EEPROM API through a read/update/readback adapter. The sketch never writes the provisioning record. An absent/invalid provisioning record or invalid journal leaves the device fail-closed and unable to complete HELLO/ARM.
- Connects `ProtocolV2Device` to a GPIO output adapter: FWD maps to D7 HIGH/D8 LOW, REV maps to D7 LOW/D8 HIGH, and PWM is limited to the protocol's 0..30 range. Safe output requests set PWM=0 and both direction pins LOW.
- Receives delimiter-framed COBS data in a fixed 194-byte workspace, invokes the existing CRC/protocol decoder, passes valid frames to the device state machine, and sends replies through the existing bounded 16-byte-per-service TX scheduler.
- No text/debug output is emitted on the binary protocol serial channel.
- Added an Arduino Uno CI compile step for this isolated sketch, copying its four required protocol headers into the sketch build directory.

Not implemented by this increment:
- ADC acquisition scheduler, per-conversion `micros()` timestamps, context/epoch capture, 12-slot ADC_BATCH producer, or sequence consumption for failed acquisition attempts.
- STATUS/telemetry production, v2 AVR resource proof (.elf/.hex/map with SRAM/stack audit), and host/firmware serial interoperability.
- Physical direction polarity confirmation, current-limit confirmation, BOD/EEPROM power-fail qualification, upload, or motor energization.

The GPIO adapter's `true` return means only that the software issued the pin writes; it is not physical feedback. This sketch is an implementation candidate, not an accepted or hardware-qualified firmware release. `HARDWARE_CURRENT_LIMIT_CONFIRMED=false` remains in force.


### V2 wire-layout reconciliation and CI evidence — 2026-11-05

The v0.5 body §4.1/§4.2 records the earlier v1 sample/batch representation (14-byte sample units and 173-byte payload). It must not be copied into the v2 sketch. The v2 appendix E representation is the one implemented by `ProtocolV2Codec.h`: 155-byte payload = 11-byte batch header + 12 × 12-byte sample units; the 12-byte v2 sample unit is timestamp_us_u32(4), channel_code(1), adc_raw(2), stage_context_token(2), acquisition_status(1), sample_flags(2). The full uint64 first_sample_sequence64 is in the batch header and slot i is first+i. The 194-byte workspace is retained; the v2 maximum wire frame is 188 bytes. Native codec validation uses these v2 offsets and length.

Sampling cadence remains unadopted. The 25/75 ms alternating schedule described in v1 §4.3 is a candidate, not permission to run acquisition at that rate. The new sketch therefore does not yet schedule or emit ADC_BATCH. Before enabling acquisition, the authority must close the v2 cadence and timing requirements and the implementation must snapshot each sample's stage token immediately before conversion, capture the conversion midpoint timestamp, and consume a sequence for every attempted slot including unavailable attempts.

Arduino Uno compile workflow run #113 / run ID 42010177306 completed success at PR #189 HEAD `d8dc58e82c7f129805a337e5b4b5746a12d87612`. The job's legacy compile, isolated v2 sketch compile, firmware source-contract checks, and artifact upload steps all succeeded. Break-in/Battery workflow run #1468 / run ID 42010177298 also completed with all four jobs successful (battery, full suite, break-in and RawLog/sequence regression). This is compile and repository regression evidence only; it is not AVR SRAM/stack qualification, host/device interoperability or hardware qualification.


### Reproducible v2 build artifact — 2026-11-05

The Uno workflow was extended to retain the separately compiled `MotoreRevV2.ino.hex` and `MotoreRevV2-build-manifest.txt` in the workflow artifact alongside the legacy firmware artifact. At exact workflow HEAD `42740e7653883e09a03dcd56eb7e8b14123d8361`, Arduino Uno Firmware Compile run #115 / ID 42011003509 succeeded, including the v2 compile step and artifact upload. Artifact ID: 13406986860 (expires 2026-11-19). Break-in and Battery run #1470 / ID 42011002691 completed with all four jobs successful. The artifact is compile output, not an AVR resource qualification or authorization to upload it to a board.


### AVR static SRAM gate — 2026-11-05

The first resource-audit attempt found 1,026 bytes of global SRAM, above the 900-byte limit. The command-result cache was then reduced by removing a redundant per-entry 16-byte session UUID: all cache lookups occur only after the current full session UUID has already been validated, and the cache is cleared whenever a new session binds. The Uno UART RX/TX ring sizes were changed to 32 bytes each using global `compiler.cpp.extra_flags`, so the sketch and Arduino HardwareSerial core share identical compile-time array bounds. A sketch-only macro override was rejected after CI exposed the class-layout mismatch warning; the override was moved to the global compile property.

At exact HEAD `91bb1d50ca42a6939a8b780283c594b082daff46`, Arduino Uno Firmware Compile run #122 / ID 42012147999 succeeded. `avr-size` reported text=10670, data=146, bss=752; therefore `.data + .bss = 898 bytes`, within the 900-byte static SRAM ceiling. The CI job also retained the HEX, ELF, linker map, size report and SHA-256 manifest in artifact ID 13408055659 (expires 2026-11-19). Native protocol v2 workflow #71 / ID 42012148002 succeeded. Break-in/Battery workflow #1477 / ID 42012148043 completed with all four jobs successful.

This closes only the static SRAM-size check for this exact build. Worst-case stack <=700 bytes, reserve >=448 bytes under the required execution paths, ISR/call nesting, UART overflow behavior under sustained traffic, and full ADC-enabled sketch memory are NOT yet proven. At 898 bytes there is only 2 bytes of headroom against the static limit; the ADC scheduler must not be added without a renewed resource budget and optimization review.


### Reduced v2 RX/TX workspace — 2026-11-05

The v2 protocol maximum wire frame is 188 bytes (155-byte ADC_BATCH payload + 29-byte header + 2-byte CRC, worst-case COBS overhead and delimiter). Added `kMaxV2WireSize=188`; the v2 TX scheduler and sketch RX workspace now use this exact bound instead of the shared 194-byte legacy ceiling. `encode_frame_in_place` now validates the caller's actual capacity against the encoded frame requirement rather than requiring the larger shared ceiling. The native TX scheduler test now allocates the exact v2 buffer.

At exact HEAD `91f4f76e2ef7d74ec29c9f27a0f1cc7b96c70cb3`, Arduino Uno compile run #125 / ID 42012704575 succeeded; `avr-size` reports text=10670, data=146, bss=740, hence `.data + .bss = 886 bytes`. Native protocol v2 run #74 / ID 42012704567 succeeded. Break-in/Battery run #1480 / ID 42012704547 completed with all four jobs successful. Artifact ID 13407238519 contains the v2 HEX, ELF, map, size report and SHA-256 manifest (expires 2026-11-19).

The previous 898-byte static footprint was reduced by another 12 bytes using the exact v2 frame ceiling. This leaves 14 bytes below the 900-byte static cap. Worst-case stack and reserve proofs remain open; static size alone is not full SRAM qualification.


### Stack-usage instrumentation — 2026-11-05

The Uno compile workflow now passes `-fstack-usage` to C++ and C compilation and stages compiler `.su` records plus a top-30 frame report in the build artifact. This is intended to support, but does not itself complete, the worst-case stack call-chain/ISR analysis. At the latest check, no Arduino workflow run was returned for the new instrumentation commit; therefore the `.su` artifact has not yet been verified. The last successful Uno build remains run #125 / ID 42012704575 at HEAD `91f4f76e2ef7d74ec29c9f27a0f1cc7b96c70cb3`, with static `.data + .bss = 886 bytes`. The current instrumentation and compile guard/comment changes are not yet covered by a newer Arduino CI result. Native protocol v2 run #78 / ID 42013704106 and Break-in/Battery run #1484 / ID 42013704193 both succeeded; all four repository test jobs passed.


### ADC attempt identity and batch TX path increment — 2026-11-05

Added the following source-level pieces:
- `ProtocolV2Device::allocate_sample_sequence64()` allocates one monotonic sequence per scheduled conversion attempt and refuses UINT64_MAX rather than wrapping; exhaustion requests safe outputs and latches `DEVICE_FAULT_STOP`.
- The v2 TX scheduler now exposes `enqueue_frame()` for a validated large telemetry payload. It accepts only when the TX path is fully idle, so ADC_BATCH cannot displace a control ACK. It encodes directly into the existing TX workspace and does not allocate a second 155-byte payload copy.
- The sketch defines an RX/ADC payload union, reusing the 188-byte RX workspace as the 155-byte ADC_BATCH construction area. Its source-level capture primitive maps channel codes 0..5 to A0..A5, snapshots the active stage token immediately before conversion, captures a per-conversion `micros()` midpoint, records raw ADC, and builds a 12-slot v2 payload. Whole batches are dropped and loss count advanced if TX is busy; no partial batch is sent.
- No cadence is selected and the capture primitive is not called by `loop()`. The 25/75 ms schedule remains a candidate only. Consequently this is not yet an active ADC acquisition scheduler and the current linked AVR image does not include the unreferenced capture primitive; its runtime SRAM/stack impact is not part of the measured image.

Native regression at HEAD `16dfa605ad4d87f6d70feff0ce2f7119ce35353a`: protocol v2 native workflow #90 / ID 42015620401 passed, including sample-sequence monotonic/exhaustion tests and large 155-byte ADC_BATCH TX encode/decode vector. Break-in/Battery workflow #1496 / ID 42015620515 passed all four jobs. Arduino compile workflow #141 / ID 42015620312 compiled the command sketch successfully, but its stack-report step failed because GNU sort was given a literal backslash-t separator. This was corrected to default whitespace sorting.

At HEAD `450f2b7505d23b29c413e6869abed2c9ad2ef862`, Arduino compile workflow #142 / ID 42015767478 passed including the corrected stack-report generation and artifact upload. The compiled linked image remains text=10924, data=146, bss=740; `.data + .bss = 886 bytes`. This does NOT measure the unreferenced ADC capture primitive. The retained artifact is ID 13409920093 (expires 2026-11-19). Native workflow #91 / ID 42015767482 passed, and Break-in/Battery workflow #1497 / ID 42015767589 passed all four jobs.

Remaining: keep the ADC capture path linked through a defined foreground scheduler interface; qualify a cadence before enabling it; test ADC sample ordering/status/sequence gaps and full batch round-trip; add STATUS/loss reporting; measure the ADC-enabled image; prove worst-case call-chain/ISR stack <=700 bytes and >=448-byte reserve. Current 886-byte SRAM result applies only to the linked command-only image, not an ADC-enabled firmware build.


### Stack report correction — 2026-11-05

The first stack artifact at run #142 contained empty `.su` files because the GCC/LTO combination did not emit usable frame records. This was not accepted as stack evidence. The Uno workflow was changed to produce a separate non-LTO analysis build with `-fstack-usage`; at run #147 / ID 42016234707, 228 non-empty frame records were emitted. The largest individual frame in that report is 168 bytes (`loop()`); the top report also includes the core ISR frames. This is only per-function frame evidence, not the required worst-case nested call-chain plus ISR stack proof. The stack parser was then corrected to parse GCC tab-delimited records and retain full/top-30 reports. At HEAD `a70c5cfd4d8144699a4f75fb236f42b49207145c`, Arduino compile workflow #148 / ID 42016688697 passed; the parser reported 228 records and largest individual frame 168 bytes. Artifact ID 13409287960 (expires 2026-11-19) contains the HEX/ELF/map and parsed full/top-30 stack reports. Native workflow #97 / ID 42016688703 passed, and Break-in/Battery workflow #1503 / ID 42016688698 passed all four jobs.


The AVR GCC 7.3 toolchain bundled with Arduino AVR core 1.8.8 rejects `-fcallgraph-info=su`; that optional compiler flag was tried, failed at compile, and was removed. The next resource-audit increment retains `avr-objdump -Cd` disassembly alongside the map and `.su` records so call edges can be reviewed manually. This is a tooling limitation, not a firmware test pass.


### TX workspace ownership correction and bounded ADC attempt helpers — 2026-11-05

The earlier source-level ADC capture implementation briefly staged ADC_BATCH in the RX workspace union and passed it to the TX scheduler. That implementation violated design v0.5 §7.3 and is superseded. The current implementation uses distinct 188-byte RX and TX workspaces; the TX scheduler acquires its own TX workspace and writes the 155-byte ADC_BATCH payload directly at the payload offset. No extra ADC payload staging buffer or complete-frame shadow is allocated. A control reply received while a batch is being built is retained in the bounded pending-reply slot; foreground TX service discards the incomplete batch and sends the control reply. STOP output-safe action occurs synchronously in the device state machine before the ACK is queued. STOP, DISARM, and HELLO boundaries explicitly discard partial batches.

ADC attempt helpers now use the AVCC reference, ADC prescaler 128, a 2 ms reference-settling delay, and a bounded 2 ms conversion wait instead of Arduino `analogRead()`. Each successful or failed attempted conversion consumes exactly one uint64 sample sequence and carries a per-conversion midpoint timestamp and stage token sampled before conversion. Named statuses are OK=0, PRECONDITION_INVALID=1, CONVERSION_TIMEOUT=2, NOT_ACQUIRED=3; failed attempts carry raw=0xFFFF. Timeout disables the ADC, so later attempted slots become PRECONDITION_INVALID. A separate helper records NOT_ACQUIRED only when a future scheduler can identify a deliberately missed scheduled slot.

Native protocol v2 workflow #113 / run ID `42027088527` passed at code HEAD `66c57f9d6f482f9aaabad2152e84c1d1b84831f3`. The added test decodes a full ADC_BATCH and verifies all four acquisition status codes and raw sentinel semantics; existing tests verify direct TX workspace assembly and STOP preemption. Arduino Uno compile workflow #164 / run ID `42027088535` also passed at that code HEAD. Linked command-only image size is text=11624, data=146, bss=746; static allocation 892 bytes (8 bytes below the 900-byte cap). The command-only nested stack audit remains 292 bytes; see `310-5-avr-resource-audit.md`.

Qualification remains incomplete: neither capture helper is called by `loop()`; no cadence is approved; no scheduler/deadline/overrun accounting, STATUS/loss-counter reporting, complete loss-window accounting, transport-evidence persistence, or ADC-enabled resource proof exists. The 892-byte SRAM result and 292-byte stack bound are for the linked command-only image and cannot be carried over to a scheduler-enabled image. With only 8 bytes of static headroom, the ADC-enabled implementation will likely require a deliberate SRAM reduction/re-layout before it can meet the 900-byte limit. No hardware interaction was performed.


### Per-attempt loss accounting and linked ADC resource recheck — 2026-11-05

A follow-up review found the partial-batch drop counter initially counted one dropped batch rather than every unretained sample attempt. The sketch now uses saturating uint32 addition and accounts each unretained attempt: failed TX workspace acquisition adds one; aborting a partial batch adds its accumulated slot count; an append failure adds prior partial slots plus the current attempt; a full-batch enqueue/validation failure adds 12. Any valid control reply preempts and discards an incomplete ADC batch before its ACK is queued, after STOP's synchronous safe-output action. The sequence allocator continues to advance for every attempt already scheduled, so host sequence gaps remain the authoritative sample-identity evidence.

The normal production build at code HEAD `6c3492d28d08ed146e0e51dbf0e368bd85cbf277` (Arduino Uno Firmware Compile workflow #181 / run ID `42029342721`) reports text=11536, data=146, bss=747; static allocation **893 bytes**, 7 bytes below the 900-byte limit. The compile-only ADC-helper audit image (macro `M4WD_ADC_RESOURCE_AUDIT`, not uploaded) reports text=12652, data=146, bss=749; static allocation **895 bytes**, 5 bytes below the limit. The audit image links both `capture_adc_attempt()` and `record_not_acquired_attempt()`; its stack report retains the 23-byte `append_adc_attempt()`, 25-byte `encode_frame_in_place()`, 17-byte `validate_payload()`, and 168-byte `loop()` frames. The deepest ADC path including the active UART TX ISR is bounded at 266 bytes; the command/ACK path remains the larger 292-byte bound. With audit-image static allocation, `2048 - 895 - 292 = 861` bytes remain, 413 bytes above the 448-byte reserve. Artifact ID `13415696144` contains both production and audit ELF/HEX/map/disassembly/stack records (expires 2026-11-19). Detailed arithmetic is in `310-5-avr-resource-audit.md`.

The v2 payload currently carries only the low 8 bits of loss_counter in ADC_BATCH and the design says counter saturation must set a SATURATED flag. However, v2 batch_flags and sample_flags are reserved-zero, and the 16-byte STATUS payload has no defined saturation flag field. Firmware now saturates at UINT32_MAX and does not wrap, but it does NOT claim to emit the separate SATURATED flag or full counter in STATUS; the wire-level flag representation and STATUS emission remain explicit unresolved design/integration work. RX overflow, COBS failure, oversize, and TX backpressure reason counters are also not yet implemented.

No sampling cadence or loop scheduler has been enabled. The linked ADC audit is compile-only and does not exercise conversion or physical hardware. No hardware interaction occurred.
