# MINI4WD AI SYSTEM

## UI Controller Integration Status

Updated: 2026-08-07

## Current Entry Point

`app/main.py` is the application entry point and creates the PyQt MainWindow.

Current flow:

```
main.py
  ↓
MainWindow
```

## Target Flow

```
main.py
  ↓
ApplicationBuilder
  ↓
BreakinController
  ↓
SerialController
  ↓
Arduino

MeasurementManager
  ↓
Measurement
  ↓
AnalysisEngine
```

## Integration Decision

The UI should not create hardware controllers directly.

ApplicationBuilder remains responsible for dependency creation and injection.

## Remaining Work

1. Pass ApplicationContext to MainWindow
2. Connect UI start action to BreakinController.start()
3. Execute mock integration test
4. Verify real Arduino communication path
