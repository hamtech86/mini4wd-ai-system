# 310-5 unified integration status — 2026-11-06

This is a draft integration record, not a formal stage acceptance.

## Combined source tree

The unified candidate combines:
- Host protocol-v2 session, durable command intent, transport Evidence, SequenceController, RawLog ADC_SAMPLE persistence, and per-channel loss accounting.
- Isolated MotoreRevV2 firmware, device state machine, EEPROM boot identity journal, bounded TX scheduler, six-channel ADC cadence scheduler, and ADC_BATCH production.
- Native protocol-v2 tests and the Arduino Uno compile/resource-audit workflow.

The ADC acquisition cadence is the adopted T+0 ms / T+25 ms / T+100 ms pattern, channel order A0,A1,A4,A5,A2,A3 per scan, two scans per 100 ms. Every scheduled slot consumes a device-owned uint64 sequence; unavailable slots are NOT_ACQUIRED and stage-unresolved. The foreground loop processes RX before one ADC slot and services TX in bounded chunks.

## Exact verification evidence

### Host-only candidate before the unified PR

Host HEAD 60c60aec9f90179e87949ca460256dd1f94821c4:
- Actions run 42088432194.
- Break-in, Battery, RawLog/Sequence, and full pytest jobs all succeeded.
- Full suite: **580 passed, 2 xfailed in 14.45s**.

### First unified firmware+host source-tree run

Unified HEAD d2fb10a72de9e69dd39863ba500a9742658c760c:
- Native protocol-v2 workflow 42088179039: success.
- Arduino Uno compile/resource workflow 42088179331: success.
- Break-in and Battery workflow 42088179153: three of four jobs succeeded; full suite failed only because a newly added test expected the literal two-character sequence backslash-n rather than a newline. The fixture was corrected and independently verified on host HEAD 60c60aec9f90179e87949ca460256dd1f94821c4 (580 passed, 2 xfailed).
- The corrected host files have been copied into this unified branch. This exact combined HEAD must be rerun before considering the unified CI green.

### AVR memory evidence from the unified firmware build

On unified HEAD d2fb10a72de9e69dd39863ba500a9742658c760c, Arduino Uno Firmware Compile run 42088179331 succeeded:
- Production integrated sketch: .data 146 B + .bss 615 B = **761 B**.
- ADC audit image: .data 146 B + .bss 616 B = **762 B**.
- Largest individual GCC frame: 171 B. The reviewed conservative nested stack bound is **295 B**.
- Using the larger static image: 2048 - 762 - 295 = **991 B** remaining, 543 B above the 448 B reserve.
- The audit build is compile-only; no board was connected or programmed.

## Remaining acceptance boundaries

- T09/T15: host STOP writer timeout is bounded in software; physical independence of the STOP path, MCU STOP parsing under actual UART load, L298N cutoff and measured stop latency remain unqualified.
- T10/T17: per-session command-intent and transport-Evidence sidecar path factories are now integrated. Package/sidecar backup-restore and production startup/recovery orchestration remain to be verified.
- T18: approved target Linux host/storage 10,000-sample fsync profile remains NOT RUN. Container overlayfs measurements are not a substitute.
- ATmega328P BOD/voltage-monitor behavior, EEPROM power-fail integrity, current limit, direction polarity, analog calibration/settling and hardware interoperability remain NOT RUN.
- No Arduino upload, serial hardware connection, motor energization, EEPROM/fuse operation, 310-second measurement or physical test was performed. HARDWARE_CURRENT_LIMIT_CONFIRMED=false remains unchanged.

Formal T01–T18 PASS and 310-5 acceptance remain pending exact unified-head CI, remaining software verification, and separate authorized hardware qualification.


## 2026-11-06 continuation — unified CI, Evidence bundle, and boot provisioning

### Exact unified source/test verification

Unified code/test HEAD 4ec8a14a8dc273227a8e1b98e7a14223360e11ff:
- Break-in/Battery workflow run 42090719264: all four jobs succeeded; full suite **588 passed, 2 xfailed in 12.13s**.
- Native protocol-v2 workflow run 42090718783: success.
- Arduino Uno Firmware Compile run 42090718935: success, including production MotoreRevV2, compile-only ADC resource-audit image, and the separate guarded EEPROM provisioner.
- The subsequent 695d8c09b9e8d85067398394ed865b3cd4c01aa0 commit adds only the provisioning procedure document.

### T10/T17 companion Evidence bundle now implemented

- RawLog v2 remains unchanged: exactly manifest.json + records.jsonl.
- The external transport Evidence sidecar now has a deterministic per-session location, a durable companion manifest containing both RawLog file hashes plus the Evidence file hash-chain head/count, and a verifier that detects tampering.
- A backup/restore regression copies the two-file RawLog package and the external Evidence directory to a new root, then verifies the restored pair.
- SequenceController normal completion now writes the companion manifest after RawLog finalization. If this step fails, it writes .310-evidence-reconciliation-required and blocks re-arm on restart. Symlinked reconciliation markers are rejected.
- This closes the software-side inventory/restore mechanism; it does not prove an actual production backup medium or power-loss recovery.

### EEPROM provisioning path

- Added a separate one-shot ProvisionBootIdentity sketch. It has no startup write, requires PROVISION followed by CONFIRM-310-BOOT-ID, writes only EEPROM 256–259, verifies readback, and refuses if journal bytes 0–255 are not erased or if partial data is unexpected.
- The shared four-byte record is tested in native C++; the provisioning sketch is compiled in CI only. It was not uploaded or run.

### Remaining gates

T09/T15 still lacks qualified physical independence of the STOP writer/path, measured MCU/driver cutoff and actual stop latency. T18 remains NOT RUN on the approved target Linux host/storage. EEPROM brownout/power-fail, BOD/voltage monitor, current-limit, direction polarity, analog calibration/settling, sustained UART load and physical interoperability remain NOT RUN. No hardware operation was performed; HARDWARE_CURRENT_LIMIT_CONFIRMED=false remains unchanged.

This exact software verification is evidence of integrated host/firmware source and automated tests, not formal 310-5 acceptance. Formal T01–T18 acceptance and stage handoff remain under upper-command review.


## 2026-11-06 continuation — STOP endpoint guard and strict T18 profile

### T09/T15 host-side STOP dispatch hardening

- Added IndependentPySerialStopWriter with its own pySerial object, 100 ms write timeout and 100 ms flush deadline (200 ms combined bound).
- The protocol-v2 RawLog session factory now refuses a real serial transport unless a callable independent STOP endpoint is supplied, its worst-case bound is below the 250 ms STOP caller deadline, and its resolved device path is distinct from the command port. It also rejects matching character-device IDs where the OS exposes them.
- The independent STOP endpoint is opened before the normal command transport. Session disconnect closes both. A non-blocking writer lock rejects concurrent STOP frames instead of interleaving them; unknown write/flush outcome latches the writer fail-closed.
- This is a software architecture and configuration guard only. A different tty path does not prove a separate electrical safety controller, hardware inhibit or L298N cutoff. No qualified external safety controller/interlock is presently connected or physically tested; T09/T15 physical qualification remains open.

### T18 profile cannot silently use smoke-test parameters

- The CLI now defaults to 10,000 samples, a fixed 10,000 ms stage, a 1,000 ms STOP reserve and a 1,000 ms additional margin.
- The runner rejects fewer than 10,000 samples, any non-10,000 ms stage, reserve/margin below 1,000 ms, and a missing or symlinked output directory. The target directory must pre-exist on the approved storage.
- The target Linux host/storage run remains NOT RUN. These guards prevent a zero-reserve/zero-margin smoke run from being mistaken for the adopted T18 profile.

### Exact unified candidate verification after these changes

Code/test HEAD 16add01e3d72440cfd019c0a59f78dc616944470:
- Break-in/Battery workflow 42092849420: all four jobs succeeded; full suite **599 passed, 2 xfailed in 16.90s**.
- Native protocol-v2 workflow 42092849183: success.
- Arduino Uno Firmware Compile workflow 42092849215: success.
- The source/test head is newer than the earlier 588-test run. The later changes are host STOP endpoint validation and strict T18 profile guards/tests; firmware source is unchanged.


## 2026-11-06 continuation — real pySerial PTY STOP separation test

- Added a Linux PTY integration test using real pySerial objects rather than only mocked serial ports.
- The command PTY is deliberately filled until its bounded write times out. The test then sends a real protocol-v2 STOP_REQ through the independent STOP PTY and decodes the received frame, verifying that the STOP endpoint remains usable when the command endpoint is blocked.
- The protocol-v2 session constructor itself now enforces the distinct bounded STOP endpoint for any transport exposing a real serial port; callers cannot bypass the factory guard by constructing the session directly.
- Unified code/test HEAD 4e79c4ff5cb76a5defe87f8420301826f1890112: all four host jobs passed; full suite **600 passed, 2 xfailed in 20.04s**. Native protocol-v2 and Arduino Uno compile/resource jobs also passed on that head.
- This is an OS/pySerial software integration test with PTYs. It does not emulate the external safety controller's electronics, the Uno UART parser, L298N enable gate, or physical motor cutoff.


## Latest verification superseding earlier 600-test count

The PTY regression was tightened to send and decode an actual protocol-v2 STOP_REQ frame through the separate STOP endpoint after the command PTY write timeout. A direct-constructor bypass regression was also added. The subsequent code/test HEAD e35d70cb2025e39e9b8b2a2de6d1476c0cc7d588 passed:
- Break-in/Battery run 42093964984: **601 passed, 2 xfailed**; all four jobs succeeded.
- Native protocol-v2 run 42093964831: success.
- Arduino Uno compile/resource run 42093964736: success.

The current branch head c8549c2c35cecdd26d5be8048ea713deee848074 adds documentation only; its corresponding full suite run 42094107820 also passed **601 passed, 2 xfailed**, native run 42094107595 passed, and Arduino compile/resource run 42094107676 passed.


## 2026-11-06 upper-command continuation — T18 host fsync profile limited acceptance

The approved target Linux host/storage run has now completed. This supersedes the earlier T18 `NOT RUN` statements above **only for the host-filesystem synthetic fsync profile**.

- Profile: `310-5-T18-fsync-v1`; 10,000 file fsync + 10,000 directory fsync samples; 10,000 paired samples.
- Host: Linux x86_64, kernel `5.15.0-190-generic`, Python 3.10.12.
- Storage: `/dev/sda3`, ext4, mount point `/`, options `rw,relatime,errors=remount-ro`.
- Output: `~/mini4wd-ai-system/artifacts/310-t18-run/`.
- Script exit code 0; wall time 14m44.746s; file and directory fsync failures both 0.
- Paired latency: p50 66.155738 ms; p95 72.162060 ms; p99 110.172843 ms; p99.9 261.742767 ms; maximum 684.258623 ms.
- Available profile budget 9,000 ms. p99.9 + 1,000 ms margin = 1,261.742767 ms; maximum + 1,000 ms margin = 1,684.258623 ms. Both are below budget; `profile_within_budget=true`.
- CSV: 10,001 lines including header; SHA-256 `1a0891adc4d68905d30ac190f833bb94244cc031c061c3fdd4ff47e8bfaaa420`, matching the JSON report. `sha256sum -c 310-fsync-report.sha256` returned OK.
- Formal record: `docs/310/310-5-t18-host-fsync-profile-acceptance-2026-11-06.md`.

Upper-command disposition: **limited PASS for the synthetic host-filesystem fsync profile only**. This does not prove the complete production RawLog save/finalize/recovery pipeline meets the 10-second stage budget, nor power-loss durability. The benchmark's paired sum is a profile estimate, not a guarantee for a different journal workload. Its 14m44.746s runtime is the time to run the benchmark, not the duration of a production stage.

T09/T15 physical STOP independence, MCU/driver cutoff and measured stop latency remain unqualified. EEPROM brownout/power-fail, BOD/voltage monitor, current limit, direction polarity, analog calibration/settling, physical serial interoperability and physical 310-second measurement remain NOT RUN. No Arduino upload, serial hardware connection, motor energization, EEPROM/fuse operation or physical test occurred. `HARDWARE_CURRENT_LIMIT_CONFIRMED=false` remains unchanged.

Formal 310-5 acceptance and stage handoff remain pending. PR #190 remains Draft/Open/Unmerged; no merge or hardware authorization is granted.
