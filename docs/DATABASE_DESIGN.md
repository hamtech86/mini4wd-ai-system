# DATABASE DESIGN

## Purpose

Database stores measurement history and analysis results.

## Design Principles

- Measurement data is preserved.
- Analysis can be repeated.
- Version information is stored.

## Main Tables

### measurement_session

Stores execution sessions.

Example fields:
- session_id
- instance_id
- device_type
- device_model
- firmware_version
- analysis_version
- start_datetime
- end_datetime
- result
- notes

### motor_instance

Stores individual motor information.

### breakin_log

Stores motor break-in measurements.

Fields include:
- timestamp
- voltage
- current
- rpm
- temperature
- pwm
- state

## Rules

Analysis Engine must not directly access database.

Flow:
Database
↓
Controller
↓
Analysis Engine
↓
Analysis Result
