# MINI4WD AI SYSTEM UI Design

## Framework

Python + PyQt5

## Purpose

Provide operation, monitoring, and result visualization for measurement devices.

## Planned Modes

- Mode1: Motor break-in / device control
- Mode2: Battery evaluation
- Mode3: Battery training support
- Mode4: Motor and battery pairing
- Mode5: Database management

## Display Items

Motor:
- Voltage
- Current
- RPM
- PWM
- Temperature
- Evaluation result

Battery:
- Voltage
- Current
- Power
- Capacity
- Internal resistance

## Design Rules

- UI communicates with Controller.
- UI does not directly control hardware.
- Measurement data is stored as records.
- Analysis results are displayed separately.