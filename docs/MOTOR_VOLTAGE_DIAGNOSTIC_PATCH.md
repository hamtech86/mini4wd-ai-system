# Motor Voltage Diagnostic Patch

## Purpose

Diagnose the mismatch between the motor terminal voltage measured by a multimeter (observed 1.8-7.0 V) and the firmware `motorVoltage` value (observed down to approximately -17 V).

## Current firmware facts

- `PIN_VM1 = A4`
- `PIN_VM2 = A5`
- `rawVM1` and `rawVM2` already exist in `SensorData`.
- `readMotorVoltage()` currently reads A4 and A5 and calculates each side using `DIVIDER_GAIN = 5.7`.
- `motorVoltage = voltage1 - voltage2`.
- Existing DATA CSV must not be changed during diagnosis because the current parser depends on the established field order.

## Safe diagnostic interface

Add a serial command `SENSOR` that does not alter the DATA CSV schema and returns the latest values:

```text
SENSOR,VM1_RAW=<raw>,VM2_RAW=<raw>,VM1_V=<voltage1>,VM2_V=<voltage2>,MOTOR_V=<motorVoltage>
```

The command must only report already-calculated sensor state. It must not modify PWM, motor direction, state, or calibration.

## Required test

1. Upload the diagnostic firmware.
2. Run the motor at a fixed PWM.
3. Measure motor terminal voltage with the multimeter.
4. Send `SENSOR` repeatedly.
5. Record:
   - VM1_RAW
   - VM2_RAW
   - VM1_V
   - VM2_V
   - MOTOR_V
   - multimeter motor-terminal voltage
6. Compare the values before changing any divider gain or sign.

## Important

Do not invert the sign or apply an empirical correction yet. The first objective is to determine whether the error originates from ADC input wiring, divider/reference calculation, or the A4-A5 differential measurement topology.

The existing `000001` Motor Instance ID and DATA schema remain unchanged during this diagnostic stage.
