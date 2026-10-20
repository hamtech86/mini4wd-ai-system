# MOTOR_BREAKIN_V3 Hardware Test Procedure

## Purpose

Safely validate direction-specific INPUT voltage control before running the full TuneBasic recipe.

## Preconditions

- Use the motor device on `/dev/ttyACM0` only.
- `/dev/ttyUSB0` is the battery-discharge device; do not select or open it for motor control.
- Firmware is already flashed. Do not reflash as part of this test.
- Secure the motor/chassis and keep an emergency stop available.
- Confirm that the UI identifies the connected device as `MOTOR_BREAKIN_V3`.
- Confirm the displayed direction, PWM, V4/Input Voltage and V5 measurements update.
- Do not run `TUNE_BASIC` for this first hardware check.

## Test recipe

Select `TUNE_BASIC_INPUT_3V_CHECK`. This isolated recipe contains only two 10-second stages and does not include any 9 V stages:

1. `CHECK_FWD_INPUT_3V`: FWD, target V4 / `voltage1` = 3.00 V, PWM limited to 35–120.
2. `CHECK_REV_INPUT_3V`: REV, target V5 / `voltage2` = 3.00 V, PWM limited to 35–120.

## Operator checks

1. Start the limited recipe only after all preconditions are met.
2. During FWD, confirm the controller adjusts PWM based on V4 / Input Voltage, not `motor_voltage`.
3. During REV, confirm the controller adjusts PWM based on V5 / Input Voltage, not the signed `motor_voltage`.
4. Stop immediately if the selected input-side voltage moves away from the target, the displayed readings are invalid/missing, direction does not match the stage, the motor behaves unexpectedly, or any safety limit is reached.
5. If either direction cannot approach 3.00 V within the limited stage, stop and record the RawLog; do not proceed to the full TuneBasic recipe or any 9 V stage.

## Acceptance criteria

- The FWD stage uses V4 / `voltage1` for voltage feedback.
- The REV stage uses V5 / `voltage2` for voltage feedback.
- PWM remains within 35–120 during this limited check.
- Negative signed `motor_voltage = V4 - V5` measurements in REV are accepted by the measurement parser and remain signed.
- Missing or invalid control measurements are rejected, not fabricated as zero.
- The operator can stop the test immediately.

This procedure is an operator-supervised hardware check, not approval to run the full TuneBasic recipe. Do not merge the implementation until CI and this real-device check pass.
