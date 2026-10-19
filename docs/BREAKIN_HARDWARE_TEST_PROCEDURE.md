# MOTOR_BREAKIN_V3 Hardware Test Procedure

## Purpose

Verify the real device communication path before full break-in execution.

## Flow

PC
↓
Break-in Controller
↓
SerialManager
↓
USB Serial
↓
Arduino MOTOR_BREAKIN_V3
↓
Motor Driver
↓
Motor

## Pre-check

- Arduino connected
- Serial port confirmed
- Motor power supply connected
- Emergency stop available

## Test Sequence

1. Open serial communication
2. Confirm device information response
3. Send motor start command
4. Confirm forward rotation
5. Change PWM value
6. Confirm stop command
7. Confirm emergency stop behavior
8. Receive CSV measurement output

## Acceptance Criteria

- No communication errors
- PWM control works
- Direction control works
- STOP immediately disables motor output
- Measurement stream is received

## Notes

This procedure validates the control path only. Performance evaluation is handled by the Analysis Engine after Measurement acquisition.


## TuneBasic INPUT-voltage preflight (Issue #94)

This is a limited control-direction check, not approval to run the full TuneBasic recipe.
Use only the dedicated `INPUT_VOLTAGE_CHECK` recipe when it is available in the application.
Do not select `TUNE_BASIC` for the first hardware check: it continues into the 9 V stages.

### Preconditions

- Confirm the motor controller is `/dev/ttyACM0`. `/dev/ttyUSB0` belongs to the battery discharger and must not be opened for this test.
- Confirm the motor is secured, wheels are clear of the bench, and an accessible physical power switch / emergency stop is available.
- Confirm firmware identification is `MOTOR_BREAKIN_V3`, FW `3.00`, build `ACS-CAL-LOG-20261013-01`.
- Start with a motor whose condition is known; do not use a valuable or already-hot motor for the first check.

### Limited test

1. Select `INPUT_VOLTAGE_CHECK`, not the full `TUNE_BASIC` recipe.
2. Start the check and watch Input Voltage, Motor Voltage, DIR, PWM, and the error/status display.
3. During FWD, confirm the control target is `voltage1 / V4 = 3.00 V`; during REV, confirm the target is `voltage2 / V5 = 3.00 V`.
4. Stop immediately if the input-side voltage does not move toward 3.00 V, the direction is wrong, telemetry becomes invalid, PWM reaches its configured ceiling without approaching target, or current/temperature safety trips.
5. Confirm PWM returns to zero at the end and the application reports completion without a serial or measurement error.
6. Save the generated RawLog for review; do not edit or normalize it.

### Gate

Passing this check permits review of the measured control response only. It does **not** authorize the full TuneBasic 9 V ramp/hold stages. Full recipe execution remains blocked until the limited test log and UI/error behavior are reviewed.
