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


## Motor Benchmark Identification (Migration 003)

Benchmark identification is split into two independent dimensions:

- benchmark_type_code
  - STANDARD
  - FULL_PACKAGE
- voltage_control_mode
  - TERMINAL
  - INPUT

This permits all four combinations to be represented:

- STANDARD + TERMINAL
- STANDARD + INPUT
- FULL_PACKAGE + TERMINAL
- FULL_PACKAGE + INPUT

### Compatibility rule

The existing measurement_session.benchmark_type value is retained as a legacy/display-compatible field. Existing rows are not rewritten or reclassified by Migration 003.

Historical rows receive NULL in the new canonical fields until their acquisition method is explicitly known. In particular, STANDARD_3V30S is not silently converted to STANDARD + INPUT; its legacy meaning remains available for compatibility.

voltage_control_mode=TERMINAL is the explicit classification for the existing terminal-voltage-fixed acquisition method. INPUT is reserved for the new input-side-voltage-fixed method.

RawLog bodies are outside this migration boundary and are never modified.

### Relationship

measurement_session remains the classification anchor:

motor_instance -> measurement_session -> measurement

RawLog records continue to reference the session through measurement_session_id.

A new INPUT benchmark must write the canonical pair to its session. Database migration itself does not alter benchmark control logic or TuneBasic.
