# Motor Break-In Device — Wiring Reference

**Status:** Physical wiring notes supplied by the user on 2026-10-09; firmware definitions take precedence where pin assignments or ADC divider ratios conflict.
**Firmware reference:** `firmware/motor/MotoreRev.ino` (`MOTOR_BREAKIN_V3.00`).
**Purpose:** Keep the reported hardware wiring and firmware-derived assumptions together for implementation and diagnostics. This document is not a substitute for a verified schematic.

## 1. Power path

Reported path:

1. 100 V AC mains outlet
2. AC adapter converts mains AC to DC; nominal output is reported as 12 V DC
3. Physical power switch
4. 2200 µF electrolytic capacitor in parallel with 0.1 µF capacitor
5. ACS712 5 A sensor #1 (high-side current measurement)
6. L298N motor driver
7. Motor positive-side output / voltage-sense node V4
8. Motor
9. Motor negative-side output / voltage-sense node V5
10. L298N GND-side return
11. ACS712 5 A sensor #2 (low-side return current measurement)
12. GND

A 0.1 µF capacitor is reported directly across the motor terminals.

Arduino Uno is powered separately from the PC over USB (5 V).

> Safety note: verify the adapter's label and output polarity before powering the device. The description above records a 12 V DC adapter, not 12 V AC. Do not work on the mains side while energized.

## 2. Arduino pin assignment

| Arduino pin | Reported connection | Firmware-defined use |
|---|---|---|
| A0 | ACS712 #1 | `PIN_ACS1`, current1 |
| A1 | ACS712 #2 | `PIN_ACS2`, current2 |
| A2 | KY-04 | `rawMagnetic` / `magneticLevel` (firmware labels this as magnetic sensor input) |
| A3 | 10 kΩ radial-lead thermistor | `rawThermistor` / `motorTemperature` |
| A4 | Voltage divider on motor-driver output / motor-positive side | `PIN_VM1`, converted to `voltage1` |
| A5 | Voltage divider on motor-driver return / motor-negative side | `PIN_VM2`, converted to `voltage2` |
| D5 | L298N PWM input | `PIN_PWM` |
| D7 | L298N direction input IN3 | `PIN_IN3` |
| D8 | L298N direction input IN4 | `PIN_IN4` |
| USB 5 V | PC USB | Arduino power |

D5/D7/D8 are from the current firmware, not separately confirmed physical-wire observations.

## 3. Voltage divider and control interpretation

The current firmware defines:

- ADC reference: 5.0 V
- ADC maximum count: 1023
- Divider R1: 47 kΩ
- Divider R2: 10 kΩ
- Divider gain: `(47000 + 10000) / 10000 = 5.7`
- A4 is `voltage1` / VM1; A5 is `voltage2` / VM2.
- Motor terminal voltage is calculated as `voltage1 - voltage2`.

For the approved INPUT control mode:
- FWD input-side voltage is V4 (firmware VM1 / A4).
- REV input-side voltage is V5 (firmware VM2 / A5).
- Motor voltage remains the measured terminal difference, direction-aware when interpreted by the application.

**Conflict rule:** if handwritten notes and firmware disagree on pin mapping or ADC divider ratio, use the firmware as the implementation reference and report the discrepancy instead of silently changing firmware or this reference.

## 4. Sensor filtering, capacitors, and grounds (reported)

- ACS712 #1 and #2 each use a 1 kΩ resistor as part of a reported low-pass arrangement. The complete RC topology/value is not yet documented.
- Arduino 5 V rail has a reported 470 µF capacitor.
- Thermistor network: 10 kΩ radial-lead thermistor; a 100 µF capacitor is reported on the GND side, but the exact connection topology needs schematic confirmation.
- 2200 µF capacitor negative terminal is reported connected to the common sensor/measurement ground.
- Grounds reported as connected together: Arduino GND, thermistor GND, KY-04 GND, both ACS712 GNDs, voltage-divider GND, and 2200 µF capacitor negative.

The exact star-point physical location and the placement of the low-side ACS712 relative to the driver return should be confirmed against the actual device before modifying wiring.

## 5. Firmware discrepancies / confirmation items

1. `MotoreRev.ino` uses A2 as the magnetic sensor input; the user identifies the device as KY-04. Confirm the installed KY-04 module's actual signal/output pin and electrical interface. Do not assume this pin provides a calibrated RPM signal.
2. Firmware's divider ratio is explicitly 47 kΩ / 10 kΩ (gain 5.7). Use this unless the source firmware is intentionally updated and tested.
3. The voltage diagnostic sketch `firmware/motor/MotorVoltageDiagnostic.ino` uses the same A4/A5 and 47 kΩ / 10 kΩ assumptions.
4. The low-pass resistor/capacitor arrangements and the thermistor capacitor topology are incomplete in the text description; capture them in a schematic when available.
5. The adapter is confirmed in the user clarification as an AC-to-DC adapter from a 100 V mains outlet; the nominal 12 V DC output should still be verified from its label.

## 6. Change policy

- Keep this file as the durable repository reference for reported physical wiring.
- Firmware pin mapping and ADC divider values are authoritative for implementation when a conflict is found.
- Any discovered mismatch between actual hardware and firmware must be reported before code changes are made.
- Do not change RawLog fields or benchmark control behavior as part of documenting wiring.
