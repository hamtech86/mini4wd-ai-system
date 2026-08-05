MINI4WD AI SYSTEM

INTERFACE_CONTRACT.md

1. Purpose

This document defines module communication contracts.

The purpose is to prevent incompatible class definitions, dataclasses, imports, and data formats during development.

---

2. Measurement Contract

Measurement

Role:

Original measurement data container.

Rules:

- Immutable
- No analysis result fields
- No scoring fields

Measurement is the source data for all analysis.

---

3. Analysis Pipeline Contract

Measurement
      |
      v
FeatureExtractor
      |
      v
FeatureSet
      |
      v
AnalysisEngine
      |
      v
AnalysisResult

---

4. FeatureExtractor

Input:

MeasurementSet

Output:

FeatureSet

Responsibility:

Convert raw measurement data into analysis features.

Restrictions:

- No database access
- No control operation

---

5. AnalysisEngine

Input:

FeatureSet

Output:

AnalysisResult

Responsibilities:

- Performance evaluation
- Brush evaluation
- Score calculation
- Strategy generation

Restrictions:

- Must not modify Measurement
- Must not directly access Database

---

6. Analysis Components

Performance

Responsibility:

Motor performance evaluation.

---

Brush

Responsibility:

Brush condition estimation.

Required output concept:

peak_detected
peak_position
brush_condition
confidence

---

Break-in Strategy

Responsibility:

Generate recommended break-in strategy.

Strategy types:

SPEED
TORQUE
BALANCE

Restriction:

Proposal only.

Direct hardware control is handled by Controller.

---

7. Controller Contract

Responsibilities:

- Execute recipes
- Control Arduino
- Collect Measurement
- Call Analysis Engine
- Save results

Controller does not replace Analysis Engine.

---

8. Change Rule

Any change to:

- Class name
- Method name
- Input
- Output
- Dataclass
- Data format

requires architecture review before implementation.

