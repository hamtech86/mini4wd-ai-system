# Motor Analysis Hardware Check

## Purpose
Freeze the current Motor Analysis implementation as the software baseline for physical verification.

## Verification contract
- Input: measurement-derived motor voltage/current features.
- Measured RPM is not an input to the estimation path.
- Estimated RPM is reported independently at 3.0 V and 2.8 V.
- Estimated torque is reported independently at 3.0 V and 2.8 V.
- Estimated supported weight is a separate output and must not use a fixed 130 g machine weight as an estimation input.
- Brush-life output remains independent from torque estimation.

## Physical test procedure
1. Start the application.
2. Connect the motor serial device at the configured motor port.
3. Select the motor instance/model.
4. Run a motor break-in/benchmark sequence that produces a final measurement containing valid motor V/I data.
5. Confirm the Estimated Performance panel updates after the measurement.
6. Record the displayed 3.0 V RPM, 2.8 V RPM, 3.0 V torque, 2.8 V torque, and supported-weight estimate.
7. Preserve the raw measurement and displayed result together for validation.

## Pass criteria
- Application starts without an AnalysisEngine exception.
- Measurement completes without changing the raw measurement.
- All four RPM/torque estimate fields receive numeric values when their required inputs are valid.
- No measured RPM is required for the estimation calculation.
- The UI does not substitute 130 g for the supported-weight estimate.
- Any unsupported/undefined supported-weight calculation is displayed as an estimate state rather than silently presented as a physical fact.

## Current limitation
The supported-weight coefficient/formula is not to be invented or restored from an arbitrary historical coefficient. Physical verification can proceed for the V/I-derived RPM and torque outputs; supported weight remains subject to the audited definition.
