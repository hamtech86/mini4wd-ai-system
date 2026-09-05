# Motor Benchmark Specification

## 1. Purpose

This document defines the selectable benchmark measurement procedures for motor raw-log acquisition.

The benchmark is a **raw-data acquisition procedure**, not an evaluation algorithm. No score, ranking, pass/fail threshold, performance grade, or derived evaluation formula is defined here.

The purpose is to obtain reproducible and traceable raw logs that can later be used to validate calculation logic.

## 2. Benchmark selection

The operator selects one of exactly two benchmark modes for each measurement session.

| Mode | Identifier | Purpose |
|---|---|---|
| 3V / 30s | `STANDARD_3V30S` | Basic standard measurement and comparison baseline |
| Full Package | `FULL_PACKAGE` | Extended measurement including controlled PWM changes |

The selected benchmark mode **must be stored in the Library Manager / Measurement Session metadata** so that every raw log can later be identified by acquisition procedure.

## 3. Common measurement principles

- The Motor Instance is identified before measurement.
- A Measurement Session is created for each execution.
- The selected `benchmark_type` is attached to that session.
- The raw time-series log is retained as the source data.
- At minimum, the existing trusted measurement basis of **voltage, current, and time** is retained.
- PWM and measurement state/phase should also be retained where already available, so the raw log can be segmented after acquisition.
- No RPM sensor is required for this benchmark.
- No evaluation formula is applied as part of benchmark acquisition.
- No raw-log summary may replace the original time-series data.

## 4. Mode A: STANDARD_3V30S

Basic procedure:

```text
START / startup
    -> 3.0 V stable drive
    -> 30 s measurement
    -> END
```

The objective is to provide a simple common baseline for repeated measurements and individual comparison.

The exact raw time-series remains the authoritative result; the benchmark does not define what constitutes a good or bad motor.

## 5. Mode B: FULL_PACKAGE

The full package uses the following sequence:

```text
START / startup
    -> 3.0 V stable drive
    -> PWM +5 %
    -> 3.0 V return / stable drive
    -> PWM -5 %
    -> 3.0 V return / stable drive
    -> END drive
    -> END
```

Each phase is retained in the raw log with its time position and available operating values.

### 5.1 Startup

Record the startup behavior from the beginning of the session. A motor that is difficult to start must not be converted into a score or automatic failure by this benchmark.

This allows cases such as a motor whose magnetization/break-in process was unsuccessful and therefore has difficult startup behavior to be recorded in the same Library Manager framework.

### 5.2 3.0 V stable drive

Operate at the benchmark target of 3.0 V and retain the raw time-series.

### 5.3 PWM +5 % / return to 3.0 V

Increase PWM by 5 % relative to the applicable baseline PWM, retain the raw time-series, then return to the 3.0 V stable-drive condition.

The benchmark does not prescribe an interpretation of the response.

### 5.4 PWM -5 % / return to 3.0 V

Decrease PWM by 5 % relative to the applicable baseline PWM, retain the raw time-series, then return to the 3.0 V stable-drive condition.

The benchmark does not prescribe an interpretation of the response.

### 5.5 End drive

For the normal benchmark termination, **command PWM to zero immediately rather than using a fade-out**.

The reason is traceability: an immediate stop creates a clear and reproducible end point and avoids introducing an additional uncontrolled ramp condition into the benchmark.

If the acquisition system can continue logging after the stop command, the post-stop raw values may be retained as part of the same session. No interpretation of the post-stop behavior is defined here.

## 6. Full Package as a break-in / conditioning procedure

The `FULL_PACKAGE` procedure is also usable as the standard **break-in / conditioning sequence**.

The same raw-log acquisition structure is used. The Library Manager must distinguish the measurement session's purpose from the benchmark procedure when such purpose metadata exists; the benchmark type itself remains `FULL_PACKAGE`.

This avoids maintaining a separate, incompatible break-in measurement format.

## 7. Library Manager traceability

The minimum conceptual relationship is:

```text
Motor Instance
    |
    +-- Measurement Session
            |
            +-- benchmark_type
            |     +-- STANDARD_3V30S
            |     +-- FULL_PACKAGE
            |
            +-- raw log
```

The benchmark type must remain attached to the session/log record throughout later analysis and database integration.

Example:

```text
MOTOR-000001
  Session-001  STANDARD_3V30S
  Session-002  FULL_PACKAGE   (break-in / conditioning)
  Session-003  STANDARD_3V30S
```

This permits later comparison without guessing which procedure produced a log.

## 8. Repeated measurements

The same benchmark mode may be executed repeatedly on the same Motor Instance. Each execution receives a separate Measurement Session while retaining the same Motor Instance identity.

This preserves both:

- differences between motor individuals; and
- differences between repeated measurements of one individual.

The benchmark specification does not define statistical acceptance criteria yet.

## 9. Raw-log requirements

The benchmark must preserve enough information to reconstruct the measurement sequence after acquisition.

At minimum, the raw record should retain the existing measurement fields for:

- timestamp / elapsed time;
- voltage;
- current;
- PWM when available;
- measurement/session linkage;
- benchmark mode at the session level.

Phase/state labels are desirable where supported, but they must not cause loss of the underlying time-series data.

## 10. Explicit non-goals

This specification does **not** define:

- motor performance scores;
- rankings;
- pass/fail thresholds;
- torque formulas;
- RPM calculation formulas;
- brush-life formulas;
- magnetization success criteria;
- vehicle-weight formulas;
- final evaluation logic;
- machine-learning features or labels.

Those decisions remain downstream of benchmark data acquisition and subsequent logic validation.

## 11. Review / acceptance target

The benchmark design is ready for Command Tower review when the reviewer can confirm all of the following:

1. Exactly two selectable benchmark modes exist: `STANDARD_3V30S` and `FULL_PACKAGE`.
2. `STANDARD_3V30S` provides the common 3.0 V / 30 s raw-log baseline.
3. `FULL_PACKAGE` records startup, 3.0 V stable operation, PWM +5 %, return to 3.0 V, PWM -5 %, return to 3.0 V, and clear termination.
4. Difficult-start motors can be recorded without imposing an evaluation judgment.
5. `FULL_PACKAGE` can also be used as the break-in / conditioning procedure.
6. The selected benchmark mode is stored by the Library Manager / Measurement Session.
7. Raw time-series data remains the source of truth.
8. No unvalidated evaluation logic has been introduced.

Implementation is intentionally outside the scope of this specification. Any implementation or schema change should proceed only after Command Tower review/approval.
