# Motor Analysis Specification

## Status
- Current canonical specification: GitHub Issue #35
- This document is an implementation/reference document and must not override Issue #35.
- Unconfirmed formulas and coefficients must not be treated as final.

## Mandatory estimated outputs
1. Estimated no-load RPM
2. Estimated torque
3. Brush peak life cycle
4. Supported vehicle weight

All four are estimates. Estimated values must not be mixed into raw logs.

## Benchmark condition
- Voltage: **3.0 V**
- Measurement duration: **30 seconds**
- Measured RPM is not used.
- RPM input is the already-confirmed estimated no-load RPM.
- Raw sensor fields are defined by the firmware specification; do not infer additional fields here.

## Motor type / nominal-value handling
Motor analysis must be able to receive and retain the **motor type/model identity** selected for the measured motor, separately from the individual motor instance/log identity.

The motor model master contains reference nominal values such as nominal RPM, nominal current, and nominal torque. These values are **reference/master data**, not measured individual-motor results. The current master implementation includes these values in `motor_model` (for example TT2, AT2, RT2, etc.). fileciteturn15file0

When calculating individual estimated torque or the other four mandatory estimated outputs:
- motor type/model may be used as contextual/master reference information;
- nominal values must not be silently substituted for the individual measured result;
- if a calculation proposes using a nominal value as a calibration/reference factor, that role must be explicitly identified and validated;
- do not treat a nominal torque value as the individual motor's estimated torque merely because the selected motor type has that nominal value.

The initial database specification also explicitly describes the stored motor values as reference specifications and states that actual measured values are to be updated later. fileciteturn16file0

## Current torque task
The first priority is to finalize the estimated torque as a motor-benchmark value that allows comparison between individual motors and can later be placed on a torque scale compatible with simulator recipe target torque.

Inputs available to the analysis task:
- high-side current
- high-side voltage
- low-side current
- low-side voltage
- elapsed time
- confirmed estimated no-load RPM
- motor type/model identity and its master/reference information

The exact torque formula and coefficients remain unconfirmed and must be proposed/validated rather than assumed from legacy implementations.

## Supported vehicle weight
To be finalized after estimated torque is finalized. It must be derived consistently from the benchmark torque definition rather than introduced as an unrelated measured quantity.

## 2.8 V
3.0 V and 2.8 V results are treated as separate displayed estimates/conversions consistent with the confirmed RPM handling. The specific torque conversion method remains unconfirmed until approved by the command center.

## Prohibited assumptions
- Do not use measured RPM.
- Do not revive legacy formulas solely because they exist in older code/issues.
- Do not treat 130 g as a measured motor result or raw-log input.
- Do not independently redefine the canonical specification in this document.
