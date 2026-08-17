# Battery System Status

## Purpose

This document records the confirmed implementation baseline for the Battery 5A Discharge Standalone function and its boundary to the future Battery Evaluation system.

## Confirmed hardware / communication baseline

- Repository: `hamtech86/mini4wd-ai-system`
- Arduino firmware repository: `hamtech86/mini4wdprototype`
- Firmware: `2ch5Abattery/2ch5Abattery.ino`
- Arduino firmware was **not changed** for the current UI verification.
- Serial device: `/dev/ttyUSB0`
- Baud rate: `57600`
- UI: PyQt5
- Launch command:
  `python3 -m battery_system.main`

## Verified by physical test

The following were confirmed with the real device:

- Python UI startup
- Serial connection to `/dev/ttyUSB0`
- CONNECT operation
- START CH1
- STOP CH1
- START CH2
- STOP CH2
- START ALL
- STOP ALL
- Voltage display
- Measured current display
- PWM display
- Elapsed time display
- 5A target display
- 5A attainment display

The sensor values shown by the PyQt5 UI were confirmed to match the values obtained when controlling the Arduino directly through the Arduino Serial Monitor.

Therefore the following measurement path is considered physically verified:

`Sensor → Arduino → DATA frame → USB serial → PyQt5 UI`

## UI data contract at this stage

Each channel displays:

- STATE
- VOLTAGE
- CURRENT
- PWM
- ELAPSED
- TARGET
- ATTAINMENT
- INTERNAL R

Internal resistance is intentionally displayed as `-- mΩ` until an appropriate measurement procedure is implemented. No instantaneous-value shortcut is permitted as an internal-resistance estimate.

## DATA / DEBUG separation

Arduino DEBUG / INA3221 diagnostic output is not treated as measurement data.

Only the defined `DATA,...` frames are consumed as measurement data by the UI. Diagnostic output remains separate.

## Anchor policy

The physically verified Battery 5A Discharge Standalone state is the baseline for subsequent Battery development.

Do not modify the verified Arduino firmware or unnecessarily rewrite the verified discharge UI when adding higher-level functions.

The standalone discharge function must remain independently usable even when Battery Evaluation, database analysis, or Simulator functions are unavailable.

## Architecture direction

```text
Battery 5A Discharge Standalone
        |
        +-- Arduino firmware
        +-- PyQt5 UI
        |
        +-- future Battery Evaluation
                |
                +-- Database
                +-- Analysis
                +-- Simulator
```

The standalone function is a reusable lower-level capability, not a disposable copy of the application.

## Current implementation references

Recent UI serial-port fixes:

- `37e6ddf` — `fix: use battery device serial port ttyUSB0`
- `968d68e` — `fix: set battery UI default port to ttyUSB0`

Working branch at the time of physical verification: `feature/battery-5a-ui`.

## Next steps

1. Preserve this physically verified baseline.
2. Guarantee standalone startup and operation.
3. Connect the standalone discharge capability to Battery Evaluation.
4. Connect evaluation results to the database.
5. Integrate Battery data with the future Simulator.

## Non-goals for this baseline

- No Arduino firmware redesign.
- No internal-resistance estimation from a single instantaneous reading.
- No requirement to launch the complete Battery Evaluation system merely to perform a 5A discharge.

## Status

**Physical verification: COMPLETE for the scope above.**

This document is a status record, not permission to change the architecture. Architecture or interface changes require司令塔 approval and corresponding specification updates before implementation.
