# MINI4WD AI SYSTEM

## Code Structure

Updated: 2026-08-07

## Current Repository Structure

The repository already contains implementation modules. This document defines their roles and the migration target.

## Application Layer

```
app/
 ├── main.py
 ├── config.py
 └── constants.py
```

Role:
- Application startup
- Configuration management
- Runtime constants

## Controller Layer

```
controllers/
 ├── breakin_controller.py
 ├── serial_controller.py
 ├── session_controller.py
 └── database_controller.py
```

Role:
- Coordinate device operation
- Manage measurement sessions
- Connect UI and lower layers
- Avoid direct analysis logic

## Communication Layer

```
communication/
 ├── protocol.py
 ├── serial_manager.py
 ├── serial_controller.py
 └── csv_parser.py
```

Role:
- Arduino communication
- Serial protocol handling
- CSV measurement data parsing

## Measurement Layer

```
measurement/
 ├── measurement.py
 └── filters.py
```

Role:
- Store measurement values
- Filtering and preprocessing
- Maintain raw data integrity

## Analysis Layer

```
analysis/
 ├── analysis_engine.py
 ├── feature_extractor.py
 ├── brush_analysis.py
 ├── performance.py
 ├── torque_estimator.py
 ├── rpm_estimator.py
 └── weight_estimator.py
```

Role:
- Extract features
- Evaluate motor characteristics
- Generate analysis results

Design rule:

Measurement data is immutable.
Analysis modules must not directly access database.

## Firmware Layer

```
firmware/
 └── motor/
     └── MotoreRev.ino
```

Role:
- Arduino motor control
- Sensor acquisition
- Serial output

## Test Layer

```
tests/
```

Role:
- Hardware tests
- Controller tests
- Integration validation

## Current Refactoring Policy

Existing code is preserved first.

Changes are performed by:

1. Confirm existing responsibility
2. Compare with specification
3. Modify only required modules
4. Commit with clear history

## Next Implementation Target

MOTOR_BREAKIN_V3:

Arduino
↓
Communication
↓
Break-in Controller
↓
Measurement
↓
Analysis Engine
↓
Result

This structure becomes the implementation baseline.
