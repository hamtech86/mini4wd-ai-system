# MOTOR_BREAKIN_V3 Status

## Purpose

This document records the current MOTOR_BREAKIN_V3 baseline, the physically verified scope, the stable anchor, and the boundaries that must be preserved while Recipe and Analysis work continues.

## Stable anchor

Stable physical baseline:

- Tag: `stable/breakin-2026-08-16`
- Commit: `9f4024d3232e07170a55db45d3df754fdb534d59`

This anchor is the rollback/reference point for verified break-in behavior. Do not rewrite or mutate the anchor.

## Current responsibility

`main.py` is responsible for:

- Motor Instance selection
- Real-device break-in execution
- Recipe execution
- Measurement collection
- Analysis invocation
- Benchmark handling
- Result display
- Manual result/database update
- Saved-result reference
- Instance Manager launch/integration

Instance Manager is responsible for Motor Instance management, history, and comparison.

Common integration identifiers:

- `motor_model_id`
- `motor_instance_id` / `instance_id`
- `measurement_session_id`
- Benchmark RPM

Motor Model is a database master. UI hard-coding of the 15 official models is prohibited.

## Physically verified scope

The verified break-in path is:

`UI → BreakinController → SerialController → Arduino`

and includes the real-device command/measurement flow:

- RUN
- FWD
- PWM control
- DATA reception
- STOP
- Measurement persistence
- Session completion
- Analysis/result generation

The KY-024 RPM signal is reference information only and is not treated as the authoritative motor-performance value.

Formal performance evaluation is based primarily on measured motor voltage/current and Analysis-derived estimates.

## Required result values

The break-in result must expose at minimum:

1. Estimated no-load RPM
2. Estimated torque
3. Estimated brush condition / brush peak
4. Estimated compatible vehicle weight

These are Analysis results, not raw sensor values.

Required vehicle-side concepts remain separate:

- Required Torque
- Estimated / Available Motor Torque
- Torque Margin
- Compatible Weight

The legacy simple torque-to-weight conversion may remain only for compatibility and must not replace the physical weight-suitability model.

## Measurement / Analysis boundary

Measurement stores measured/raw data. Analysis derives estimates without rewriting the underlying Measurement data.

Conceptual flow:

`Motor → Voltage/Current/Time/ADC (+ reference RPM) → Measurement → Analysis → Estimated RPM/Torque/Brush/Weight`

KY-024 RPM must not be promoted to an authoritative performance measurement merely because it produces a stable value.

## Recipe direction

The long-term Recipe architecture is sequence-based.

```text
Recipe Preset
    ↓
Sequence Definition
    ↓
Sequence Executor
    ↓
Hardware Adapter / Simulator Adapter
    ↓
Measurement
    ↓
Analysis
    ↓
Result
```

Recipe is a preset of Sequences, not a collection of hardware-control branches in `main.py`.

Initial command set:

- FWD
- REV
- STOP
- REST
- FADE
- RAMP
- WAIT
- BENCHMARK

Sequence fields should support command, parameters, duration, conditions, and enabled/skip state. Skipped sequences remain recorded as `SKIPPED` in execution history.

## Current TuneBasic direction

TuneBasic is the first Recipe to be migrated toward the sequence model.

The currently intended basic process includes:

- FWD low/3V-equivalent operation
- PWM ramp
- higher-voltage-equivalent operation
- fade-out
- rest
- REV operation
- fade-out
- rest
- final 3V-equivalent benchmark

The exact PWM/phase values must remain governed by the current implementation and real-device validation; the sequence architecture must not silently change verified hardware behavior.

## Resume requirements

Resume must be tied to:

- recipe_id
- recipe_version
- sequence_id/index
- sequence status
- elapsed time
- current PWM
- direction
- condition state
- motor instance
- measurement session

Resume must be rejected when the Recipe/Version/Instance context does not match.

## Database / history boundary

Results are associated through:

`Motor Instance → Measurement Session → Measurement`

The Measurement table remains the source of truth for recorded measurements.

Result UI supports user review before database update. Automatic blind registration of a result is not the intended safety behavior because it can bind an incorrect Instance or abnormal measurement.

## Regression rules

While Recipe/Analysis work proceeds:

- Preserve the stable anchor as rollback reference.
- Do not change Arduino hardware merely to accommodate software design.
- Do not replace verified serial control with speculative abstractions without real-device validation.
- Do not treat KY-024 RPM as authoritative performance data.
- Do not rewrite Measurement data during Analysis.
- Do not collapse Required Torque and Motor Torque into one value.
- Do not remove the manual result-review/update boundary without explicit design approval.

## Next priority

1. Stabilize TuneBasic Phase 2 and later real-device behavior.
2. Connect PAUSE/RESUME to the sequence state machine.
3. Complete sequence state management.
4. Execute the complete Recipe on the real device.
5. Calibrate the four estimated result values using accumulated real measurements.
6. Expand UI sequence display/editor after the executor is stable.
7. Add Simulator Adapter after the real-device path is stable.

## Relationship to Battery system

Battery development is independent and proceeds in parallel.

The Battery 5A Standalone baseline is recorded separately in `docs/BATTERY_SYSTEM_STATUS.md`.

This document is the MOTOR_BREAKIN_V3 reference and should be consulted before modifying the motor break-in path.

## Status

**MOTOR_BREAKIN_V3 remains under active development.**

The stable anchor above is the protected physical reference. Subsequent work must be incremental and must preserve verified real-device behavior unless a deliberate regression test and replacement anchor are established.
