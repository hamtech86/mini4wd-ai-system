# Motor Analysis rebuild specification

Effective baseline: 2026-08-30 reset.

Old implementation code is not reused. This document defines the rebuilt calculation contract.

## Mandatory outputs

1. Estimated no-load RPM
2. Estimated torque
3. Brush peak life-cycle index
4. Estimated supported weight

The UI must expose 3.0 V and 2.8 V reference-voltage RPM/torque values independently, plus the brush index and supported-weight estimate.

## Inputs

- `motor_voltage` from the raw measurement
- `current_avg` from the raw measurement
- `brush_peak_current` from the raw measurement
- motor-model nominal RPM/current/torque
- nominal motor voltage (2.4 V for the supplied motor master data)

Measured RPM is not an input to Motor Analysis.
`brush_peak_current` is not a torque input.

## Calculations

### RPM

Measured operating-point estimate:

`rpm_measured = nominal_rpm * motor_voltage / nominal_voltage`

Reference-voltage normalization:

`rpm_3v = rpm_measured * 3.0 / motor_voltage`

`rpm_2_8v = rpm_measured * 2.8 / motor_voltage`

This preserves the requirement that the estimate originates from measured motor voltage and never consumes measured RPM.

### Torque

`torque = current_avg[A] * nominal_torque[g·cm] / nominal_current[A]`

The 3.0 V and 2.8 V result fields are independent reference outputs of this V/I-derived estimate. Brush peak current is excluded.

### Brush peak life-cycle

Atomic Tune is the 100% reference. For the current Cal7570 benchmark the Atomic reference peak is 1.498 A:

`brush_peak_life_cycle[%] = 1.498 / brush_peak_current[A] * 100`

This is an index, not an invented absolute number of cycles.

### Supported weight

Established torque/weight anchor:

`121.2 g·cm <-> 130 g`

Therefore:

`supported_weight[g] = torque[g·cm] * 130 / 121.2`

No fixed 130 g result is returned; 130 g is only the reference anchor in the conversion.

## Acceptance

Cal7570 raw data must pass through:

`raw V/I -> FeatureSet -> rebuilt PerformanceAnalysis -> PerformanceResult -> UI`

and produce non-empty numerical values for all four mandatory outputs, with 3.0 V and 2.8 V RPM/torque visible.

No legacy gain coefficients, `current * 10`, `voltage * 5000`, fixed output weight, or measured-RPM input are permitted.
