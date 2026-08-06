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
