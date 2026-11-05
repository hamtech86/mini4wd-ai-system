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
