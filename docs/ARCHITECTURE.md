# MINI4WD AI SYSTEM Architecture

## Overview

The system is designed as a measurement and analysis platform for Mini 4WD performance.

## Data Flow

Hardware Device
→ Communication Layer
→ Controller
→ Measurement Collection
→ Feature Extraction
→ Analysis Engine
→ Result
→ Database / UI

## Main Components

### Device Layer

Arduino based measurement devices.

Functions:
- Motor control
- Current measurement
- Voltage measurement
- RPM measurement
- Temperature measurement

### Controller Layer

Controls execution flow.

Examples:
- Break-in Controller
- Battery Evaluation Controller

Controller decides operation sequence but does not perform analysis.

### Measurement Layer

Stores raw measurement data.

Rules:
- Raw data is immutable.
- Re-analysis must be possible.

### Analysis Engine

Plugin structured architecture.

Planned modules:
- performance
- brush analysis
- diagnosis
- scoring
- recommendation
- simulator adapter

Analysis Engine does not access database directly.

## UI

PyQt5 based interface.

Functions:
- Device status
- Measurement control
- Result display
- Database management

## Version Management

The system uses:
- schema_version
- firmware_version
- analysis_version

for reproducibility.
