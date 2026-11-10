# Motor firmware targets

## Current 310 firmware

`MotoreRevV2/MotoreRevV2.ino` is the only current 310 motor firmware target. Build it for the explicitly selected ATmega328PB / 16 MHz external-clock profile using MiniCore. The board identity, oscillator, BOD fuses, reset-time electrical state, and physical safety behavior still require separate qualification.

## Retired legacy DATA26 firmware

`MotoreRev.ino` is retained only as historical legacy DATA26 source. It contains the former A0/A1 averaging and derived-field behavior and is **not** the 310 measurement firmware. A normal build intentionally fails with a compile-time error. Do not upload it to the 310 motor controller.

The `M4WD_ENABLE_LEGACY_DATA26` macro is an explicit legacy opt-in for archival compatibility work only; it does not make the sketch compliant with the current A0/A1 channel contract. Do not use that opt-in for 310 measurements, safety control, or new RawLog v2 data.

Historical RawLog v1 files and the legacy parser remain separate. This retirement does not rewrite, migrate, reclassify, or delete historical data.
