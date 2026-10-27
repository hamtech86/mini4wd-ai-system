# Supervised Physical Motor-Stop Verification

Status: **procedure/recipe definition only; not authorization to operate hardware**.

## Purpose

Verify that an explicit STOP command issued while the motor is actually rotating leads to physical cessation of rotation, and that the motor does not restart during the observation window. A STOP ACK, PWM=0 report, CI result, or serial log alone is not physical-stop proof.

## Preconditions — do not start unless all are met

1. Confirm the connected device's `INFO` response and record FW version and BUILD ID.
2. Verify that the physical firmware identity matches the reviewed firmware/protocol contract. The BUILD ID recorded in Issue #147 differs from the current source BUILD ID; if that mismatch remains unresolved, **do not run this recipe**.
3. Use the fixed FW 3.03 build only. No firmware flashing, wiring changes, or safety-threshold changes are part of this procedure.
4. Secure the motor/test fixture; install and verify a non-contact optical tachometer or other independent RPM measurement before power-on. Do not touch a rotating shaft or install a reflective marker while powered.
5. Ensure the physical power switch is immediately reachable. A second person should observe the motor and measurement where practicable.
6. Synchronize the host log and external instrument/video clocks, or record a common visible/audio time marker.

## Recipe

Select `STOP_PROOF_3V_INPUT` only after the preconditions are met.

- Control: INPUT feedback, target 3.00 V, FWD only.
- PWM: initial 60, constrained to 35–120 by the existing recipe guard.
- Maximum active phase: 10 seconds.
- The operator must press the normal STOP control while independent measurement confirms the motor is rotating, ideally about 2–3 seconds after stable rotation is observed. Do **not** wait for the 10-second phase to complete; normal phase completion is not equivalent to testing STOP while driving.
- Keep the RPM instrument recording continuously through STOP and the post-stop observation.
- Observe for at least 10 seconds after STOP. The physical stop criterion is no detected rotation/pulses and a measured RPM of zero continuously for at least 5 seconds, with no subsequent restart during the full 10-second observation window. Record the instrument's resolution/zero threshold.

## Immediate abort / failure handling

If the motor does not decelerate and stop promptly, the RPM signal is unavailable/ambiguous, the STOP result is unclear, or the serial link/identity is lost: cut physical power immediately, do not restart, and preserve all logs/video. Do not repeat the run merely to reproduce a failure.

## Evidence bundle

Use one unique test ID and retain:

- Date/time, operator, test ID, motor/device instance.
- Exact `INFO` response including FW and BUILD ID; firmware source/commit reference used for comparison.
- Recipe name/version and selected control mode.
- Raw serial transcript including ARM request/ACK, active token state if exposed, direction/PWM commands, STOP request, STOP ACK/error, and disconnect status.
- Host timestamps for rotation confirmed, STOP button action, STOP TX/RX, and observed RPM=0.
- Continuous external RPM trace/video from before STOP through the full post-stop window, including instrument model, resolution, and sample/update rate.
- If available without unsafe wiring changes, independent motor-terminal voltage/current waveform synchronized to STOP. Record the measurement method and instrument settings.
- Outcome: PASS only if rotation was independently observed before STOP, the stop event is time-correlated, RPM reaches zero within the pre-agreed stopping-time limit, and no rotation returns during the 10-second observation window. Any missing evidence is INCONCLUSIVE, not PASS.

## What this proves — and does not prove

A PASS supports the tested hardware/build/configuration and operating condition only. It does not prove all fault modes or all recipes safe, and does not replace software tests for STOP latching and stale-token rejection. CI and serial ACKs are supporting evidence, never substitutes for independent RPM observation.
