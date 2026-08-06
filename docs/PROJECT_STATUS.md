# MINI4WD AI SYSTEM

## Project Status

Updated: 2026-08-07

## Purpose

This project integrates Mini 4WD motor break-in automation, motor performance evaluation, Neo Champ battery evaluation, and future simulator functions.

## Current Architecture

Arduino Device
→ Communication
→ Controller
→ Measurement
→ Analysis Engine
→ Result
→ Database / UI

## Confirmed Modules

- Motor Break-in Controller
- Battery Evaluation Device
- PyQt5 UI
- Database design
- Analysis Engine architecture

## Motor Break-in

Goal: automate motor break-in and evaluate motor characteristics.

Main measured data:
- Voltage
- Current
- RPM
- Temperature
- PWM
- Time series behavior

## Battery Evaluation

Target battery:
- Tamiya Neo Champ NiMH

Evaluation items:
- Discharge characteristics
- Capacity estimation
- Internal resistance estimation
- Stability evaluation

## Software Design Rules

- Analysis Engine does not access database directly.
- Measurement data is immutable.
- Version information is managed.
- Modules are separated for maintainability.

## Development Status

The project is moving from prototype verification to structured implementation.

Next priority:
1. Fix repository structure
2. Consolidate specifications
3. Implement Break-in Controller
4. Integrate Measurement and Analysis Engine
