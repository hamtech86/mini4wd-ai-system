MINI4WD AI SYSTEM

SYSTEM_ARCHITECTURE.md

1. Purpose

This document defines the current system architecture baseline for MINI4WD AI SYSTEM.

The purpose is to prevent specification drift between multiple development chats and maintain a single reference architecture.

---

2. System Overview

Arduino Layer
      |
      v
Measurement Model
      |
      v
Database Layer
      |
      v
Analysis Engine V1.0
      |
      v
Break-in Controller
      |
      v
UI Layer

---

3. Layer Responsibilities

Arduino Layer

Status:
Completed

Responsibilities:

- PWM control
- Motor direction control
- Sensor acquisition
- Raw CSV transmission
- Safety stop

Restrictions:

- No analysis processing
- No scoring logic
- No database access

---

Measurement Model

Status:
Completed

Responsibilities:

- Store original measurement data
- Provide common data format between layers

Important rule:

Measurement data is immutable.

Analysis processing must not modify original measurement records.

---

Database Layer

Status:
Completed (basic)

Technology:

- SQLite

Structure:

- Repository pattern
- CRUD operation
- Transaction management

Responsibilities:

- Data persistence
- History management

---

Analysis Engine V1.0

Status:
Completed

Test:

python3 tests/test_analysis.py

Result:

PASS

Responsibilities:

- Feature extraction
- Performance analysis
- Brush analysis
- Scoring
- Strategy proposal

Directory:

analysis/

analysis_engine.py
models.py
validation.py
feature_extractor.py
performance.py
brush.py
breakin_strategy.py
scoring.py

---

Break-in Controller

Status:
Not completed

Responsibilities:

- Recipe management
- Phase management
- Arduino command control
- Measurement acquisition
- Analysis Engine connection
- Database saving

---

UI Layer

Status:
Foundation exists

Not completed:

- Controller connection
- Analysis connection
- Database connection

---

4. Development Principle

Development order:

Specification
      |
Interface Contract
      |
Implementation
      |
Test
      |
Commit

Existing architecture must not be changed without review.

