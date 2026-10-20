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


## TuneBasic INPUT-voltage focused hardware check (PR #96)

**Do not run the complete TuneBasic recipe for this initial check.** The purpose is only to verify the direction-dependent 3.00 V input target.

### Preconditions

- Use the motor device on `/dev/ttyACM0` only. `/dev/ttyUSB0` belongs to the battery discharger and must not be used for this test.
- Confirm the emergency stop is reachable and the motor is securely mounted with no load hazards.
- Confirm the device INFO response identifies `MOTOR_BREAKIN_V3` and firmware `3.00` before starting.
- Keep the test limited to the 3 V start phase; leave every other TuneBasic phase unchecked.
- Do not reflash firmware, alter wiring, or edit RawLog/DB data as part of this test.

### Test A — FWD input target

1. Select `TUNE_BASIC` and enable only `FWD_3V_START`.
2. Start the selected sequence and observe the live voltage values.
3. Confirm the controller adjusts PWM based on `V4 / voltage1` and that V4 moves toward 3.00 V.
4. Stop the sequence after the limited check; do not proceed to the 3→9 V ramp.

### Test B — REV input target

1. After the motor has stopped and the device is in a safe state, select only `REV_3V_START`.
2. Start the selected sequence and confirm control uses `V5 / voltage2`, not signed `motor_voltage`.
3. Confirm V5 moves toward 3.00 V, then stop the sequence.

### Immediate stop criteria

- No valid DATA measurement: the sequence should abort and command PWM 0.
- V4/V5 does not move toward 3.00 V, the reading is implausible, direction is unexpected, or any communication/control error occurs.
- Any stop criterion is met: stop the test and do not execute any 9 V stage or the full recipe. Record the observed error and RawLog as-is for review; do not edit the log.

### Acceptance

This focused test passes only when FWD selects V4, REV selects V5, each moves toward 3.00 V, and missing DATA stops PWM. This is not approval to run the complete break-in recipe or merge PR #96.
