# MOTOR_BREAKIN_V3 Hardware Test Procedure

## Purpose

Perform only the currently authorized, operator-supervised INPUT feedback check. A passing CI run or serial acknowledgement is not proof of physical stopping.

## Preconditions

- Use the motor Arduino on `/dev/ttyACM0` only.
- `/dev/ttyUSB0` belongs to the battery-discharge device; never select or open it for motor control.
- Do not flash firmware as part of this procedure. Confirm the connected device reports `MODEL=MOTOR_BREAKIN_V3`, `FW=3.03`, and `BUILD=EXPLICIT-ARM-STOP-ACK-20261023-01`.
- Secure the motor/chassis and keep the physical motor power switch immediately reachable.
- Confirm Input Voltage, Motor Voltage, Driver Input Current, DIR, PWM, elapsed time, and remaining time update plausibly.
- Confirm the operator can reach UI STOP and the physical power switch without delay.
- If identity is missing/mismatched, measurements are stale/invalid, or the controller is stop-latched, do not start.

## Authorized recipe: `TUNE_BASIC_INPUT_3V_CHECK` only

This limited recipe contains two 10-second stages (20 seconds nominal total) and does not include any 9 V stage:

1. `CHECK_FWD_INPUT_3V`: FWD, target V4 / `voltage1` = 3.00 V, PWM limited to 35–120, 10 s.
2. `CHECK_REV_INPUT_3V`: REV, target V5 / `voltage2` = 3.00 V, PWM limited to 35–120, 10 s.

**Do not start `TUNE_BASIC` / full TuneBasic.** Its 11-phase, nominal 510-second recipe—including 9 V stages—is visible for sequence inspection and pseudo-resume planning only. Full execution and resume remain blocked until Issue #98 is explicitly cleared.

All voltage feedback must use the input-side measurement: FWD uses V4 / `voltage1`; REV uses V5 / `voltage2`. Signed `motor_voltage = V4 - V5` is a separate terminal measurement and must not substitute for INPUT feedback.

## During the limited check

- Watch Input Voltage, Motor Voltage, Driver Input Current, DIR, PWM, elapsed time, and remaining time.
- Keep PWM within 35–120 for this check.
- Press UI STOP immediately if the direction is wrong, data becomes missing/invalid, voltage response is unexpected, a safety limit is reached, or the motor behaves unexpectedly.
- If the motor does not physically stop immediately after UI STOP, cut power with the physical switch and do not restart.
- Do not leave the system unattended. Do not proceed to full TuneBasic or 9 V operation after this check without the separate Issue #98 decision.

## Completion and evidence

- Record whether the UI completed/stopped and separately whether physical stopping was observed.
- Preserve and review the RawLog for both directions, input-side voltage feedback, current, phase transitions, and any stop discrepancy.
- Record firmware identity, UI state, RawLog evidence, physical stopping observation, and errors separately.
- A CI pass, a successful serial write, or a firmware ACK is not physical-stop proof.

Issue #98 remains the tracking point for the physical result and the explicit decision on any later full TuneBasic authorization. This procedure does not clear that gate.
