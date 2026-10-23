# MOTOR_BREAKIN_V3 Hardware Test Procedure

## Purpose

Run the configured TuneBasic INPUT recipe using the current integrated Main UI. This procedure records the actual operator checks and does not treat CI or serial acknowledgements as proof of physical stopping.

## Preconditions

- Use the motor Arduino on `/dev/ttyACM0` only.
- `/dev/ttyUSB0` belongs to the battery-discharge device; never select or open it for motor control.
- Do not flash firmware as part of this procedure. Confirm the connected device reports `MODEL=MOTOR_BREAKIN_V3`, `FW=3.03`, and `BUILD=EXPLICIT-ARM-STOP-ACK-20261023-01` before enabling operation.
- Secure the motor/chassis and keep the physical motor power switch immediately reachable.
- Confirm Input Voltage, Motor Voltage, Driver Input Current, DIR, PWM, elapsed time, and remaining time are updating plausibly before starting.
- Confirm the operator can reach UI STOP and the physical power switch without delay.
- If identity is missing/mismatched, measurements are stale/invalid, or the controller is already stop-latched, do not start; resolve that specific condition rather than treating Issue #98 as a blanket work blocker.

## Recipe

Select `TUNEBASIC (FULL INPUT)`, which dispatches the `TUNE_BASIC` recipe. Nominal configured duration is 510 seconds (8 minutes 30 seconds):

1. FWD 3.00 V start — 30 s, PWM 35–120.
2. FWD ramp 3.00 → 9.00 V — 60 s, PWM 35–245.
3. FWD 9.00 V hold — 60 s, PWM 35–245.
4. FWD fade-out 9.00 → 0.00 V — 30 s.
5. FWD rest — 60 s, PWM 0.
6. REV 3.00 V start — 30 s, PWM 35–120.
7. REV ramp 3.00 → 9.00 V — 60 s, PWM 35–245.
8. REV 9.00 V hold — 60 s, PWM 35–245.
9. REV fade-out 9.00 → 0.00 V — 30 s.
10. REV rest — 60 s, PWM 0.
11. Final FWD 3.00 V benchmark — 30 s, PWM 35–120.

All voltage-controlled stages use INPUT feedback: FWD controls from V4 / `voltage1`; REV controls from V5 / `voltage2`. Signed `motor_voltage = V4 - V5` is a separate terminal measurement and must not substitute for INPUT feedback.

## During the run

- Watch Input Voltage, Motor Voltage, Driver Input Current, DIR, PWM, elapsed time, and remaining time throughout the run.
- Common configured limits are motor temperature 70 °C, current 5.0 A, and PWM 245. Do not override the configured limits.
- Press UI STOP immediately if the motor behaves unexpectedly, direction does not match the phase, sensor data becomes missing/invalid, a configured safety limit is reached, or the measured response departs materially from the target.
- If the motor does not physically stop immediately after UI STOP, cut power with the physical switch and do not restart.
- Do not leave the running system unattended.

## Completion and evidence

- Confirm the UI reports completion and that the motor is physically stopped.
- Preserve the RawLog and inspect phase transitions, FWD/REV voltage feedback, current, temperature, and stop behavior.
- Record separately: UI completion state, RawLog evidence, observed physical stopping, firmware identity, and any errors.
- If an unexpected behavior or stop discrepancy occurs, keep the log and diagnose that concrete failure before another run. Do not infer physical safety from a passing CI job or a serial ACK alone.

Issue #98 is the place to record the physical result and any remaining safety findings; its existence alone is not a reason to stop unrelated software preparation.
