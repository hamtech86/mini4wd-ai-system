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
    -> 3.00 V stable condition established
    -> 30 s measurement
    -> END
```

### 4.1 Meaning of 3.0 V

The **3.0 V benchmark condition represents the nominal electrical condition of two dry-cell batteries used for Mini 4WD running**.

Accordingly, 3.0 V is a benchmark reference condition for relating motor measurements to practical Mini 4WD operation. It is not a claim that an actual two-cell battery pack remains exactly 3.0 V under all operating conditions.

The objective is to provide a simple common baseline for repeated measurements and individual comparison.

The exact raw time-series remains the authoritative result; the benchmark does not define what constitutes a good or bad motor.

## 5. 3.0 V stability condition

The 3.0 V stability condition is a **process-start condition**, not a measurement pass/fail criterion.

The target voltage is **3.00 V**.

The stable condition is established when the measured voltage remains continuously within:

```text
2.95 V <= V <= 3.05 V
```

for **2 seconds continuously**.

Once this condition has been established, the applicable timed measurement phase begins.

The 2.95–3.05 V / 2-second condition is used only to establish that the motor has entered the intended 3.00 V benchmark operating condition before starting a timed phase. It does not define motor quality or benchmark success.

### 5.1 Voltage deviation during measurement

After a timed measurement phase has started, the 2.95–3.05 V range is **not used as an automatic pass/fail condition**.

If the measured voltage leaves the 2.95–3.05 V range during a measurement phase:

- the measurement is not automatically interrupted;
- the session is not automatically marked as failed;
- the actual voltage, current, time, PWM, and available state/phase data continue to be retained in the Raw Log.

The observed deviation is therefore treated as measured experimental data for later analysis rather than as an implementation-time judgment.

## 6. Mode B: FULL_PACKAGE

The full package uses the following sequence:

```text
START
    -> 3.00 V stable condition established
    -> 3.00 V stable measurement × 30 s
    -> PWM +5 % relative to baseline PWM × 30 s
    -> 3.00 V return / buffer × 10 s
    -> PWM -5 % relative to the same baseline PWM × 30 s
    -> 3.00 V return / buffer × 10 s
    -> PWM = 0
    -> END
```

The **3.00 V stable × 30 s**, **PWM +5 % × 30 s**, and **PWM -5 % × 30 s** sections are timed measurement phases. The two **3.00 V return × 10 s** sections are transition/buffer phases and are not defined as comparison windows.

Each phase is retained in the raw log with its time position and available operating values.

### 6.1 Startup

Record the startup behavior from the beginning of the session. A motor that is difficult to start must not be converted into a score or automatic failure by this benchmark.

This allows cases such as a motor whose magnetization/break-in process was unsuccessful and therefore has difficult startup behavior to be recorded in the same Library Manager framework.

### 6.2 3.00 V stable drive / baseline establishment

Operate at the benchmark target of 3.00 V and retain the raw time-series.

The 3.0 V stable condition must first be established according to Section 5. The **2.95–3.05 V range held continuously for 2 seconds is the condition for starting the timed 30-second stable measurement phase**.

For FULL_PACKAGE, the **baseline PWM is the actual PWM value established while the motor is in the initial 3.00 V stable-drive condition immediately before the first PWM perturbation**.

The baseline is therefore not a separately entered nominal PWM value. It is the PWM value actually used by the control system to establish the 3.00 V benchmark condition.

The baseline PWM value must be retained in the raw log/session data when available so that the later analysis can reconstruct the applied perturbation.

### 6.3 PWM +5 % / return to 3.00 V

Increase PWM by **5 % relative to the baseline PWM** established in Section 6.2 and retain the raw time-series for **30 seconds** during the perturbation.

The purpose of this change is to create a small experimental perturbation for observing the motor's response to a PWM change, while avoiding a deliberately large PWM change that could substantially alter the motor's operating condition.

The 5 % value is an **experimental condition, not an evaluation threshold, score boundary, or final performance criterion**. Its suitability remains subject to later real-machine verification and may be revised based on acquired data.

After the +5 % perturbation, return to the **3.00 V benchmark condition for 10 seconds**. This 10-second period is a transition/buffer phase for absorbing PWM-transition transients and confirming return toward the benchmark voltage condition; it is not a defined comparison window.

Returning to 3.00 V means restoring the benchmark's voltage condition; it does not redefine the baseline PWM. The baseline PWM remains the value recorded from the original 3.00 V stable-drive condition.

The benchmark does not prescribe an interpretation of the observed response.

### 6.4 PWM -5 % / return to 3.00 V

Decrease PWM by **5 % relative to the same baseline PWM** defined in Section 6.2 and retain the raw time-series for **30 seconds** during the perturbation.

After the -5 % perturbation, return to the **3.00 V benchmark condition for 10 seconds**. This 10-second period is a transition/buffer phase and is not a defined comparison window.

The +5 % and -5 % perturbations therefore use the same reference PWM. They are not calculated successively from one another.

The purpose is to make the response to a small PWM decrease observable while keeping the experimental condition symmetric around the original baseline PWM.

The benchmark does not prescribe an interpretation of the response.

### 6.5 PWM bounds and implementation interpretation

The ±5 % perturbation is defined mathematically relative to the recorded baseline PWM:

```text
PWM_plus  = baseline_PWM × 1.05
PWM_minus = baseline_PWM × 0.95
```

The resulting command must remain within the valid PWM command range of the hardware/software implementation. If integer PWM commands are required, the implementation must use a deterministic rounding rule and retain the resulting commanded PWM in the raw log.

No additional performance meaning is assigned to the resulting PWM value.

### 6.6 End drive

For the normal benchmark termination, **command PWM to zero immediately rather than using a fade-out**.

The reason is traceability: an immediate stop creates a clear and reproducible end point and avoids introducing an additional uncontrolled ramp condition into the benchmark.

If the acquisition system can continue logging after the stop command, the post-stop raw values may be retained as part of the same session. No interpretation of the post-stop behavior is defined here.

## 7. Full Package as a break-in / conditioning procedure

The `FULL_PACKAGE` procedure is also usable as the standard **break-in / conditioning sequence**.

The same raw-log acquisition structure is used. The Library Manager must distinguish the measurement session's purpose from the benchmark procedure when such purpose metadata exists; the benchmark type itself remains `FULL_PACKAGE`.

This avoids maintaining a separate, incompatible break-in measurement format.

## 8. Library Manager traceability

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
            +-- purpose (when supported)
            |     +-- measurement
            |     +-- break-in / conditioning
            |
            +-- raw log
```

The benchmark type must remain attached to the session/log record throughout later analysis and database integration.

Example:

```text
MOTOR-000001
  Session-001  STANDARD_3V30S  (measurement)
  Session-002  FULL_PACKAGE   (break-in / conditioning)
  Session-003  STANDARD_3V30S  (measurement)
```

This permits later comparison without guessing which procedure produced a log.

## 9. Repeated measurements

The same benchmark mode may be executed repeatedly on the same Motor Instance. Each execution receives a separate Measurement Session while retaining the same Motor Instance identity.

This preserves both:

- differences between motor individuals; and
- differences between repeated measurements of one individual.

The benchmark specification does not define statistical acceptance criteria yet.

## 10. Raw-log requirements

The benchmark must preserve enough information to reconstruct the measurement sequence after acquisition.

At minimum, the raw record should retain the existing measurement fields for:

- timestamp / elapsed time;
- voltage;
- current;
- PWM when available;
- measurement/session linkage;
- benchmark mode at the session level.

For FULL_PACKAGE, the baseline PWM and the commanded PWM during each perturbation should be retained where supported, so that the +5 % / -5 % experimental condition can be reconstructed without inference from later calculations.

Phase/state labels are desirable where supported, but they must not cause loss of the underlying time-series data.

Voltage deviations during timed measurement phases must likewise remain in the Raw Log; they must not be converted into an automatic benchmark failure or discarded from the time-series.

## 11. Explicit non-goals

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

The ±5 % PWM change is also **not** an evaluation threshold or performance criterion. It is a provisional experimental perturbation condition whose validity will be checked against real-machine data.

The 2.95–3.05 V / 2-second stability condition is a **measurement-phase start condition only**. It is not an evaluation threshold, and leaving that voltage range after a timed measurement phase has started does not by itself cause automatic failure or termination.

Those decisions remain downstream of benchmark data acquisition and subsequent logic validation.

## 12. Review / acceptance target

The benchmark design is ready for Command Tower review when the reviewer can confirm all of the following:

1. Exactly two selectable benchmark modes exist: `STANDARD_3V30S` and `FULL_PACKAGE`.
2. `STANDARD_3V30S` provides the common 3.0 V / 30 s raw-log baseline, with 3.0 V representing the nominal two-dry-cell Mini 4WD running condition.
3. A 3.00 V stable condition is established by continuously remaining within 2.95–3.05 V for 2 seconds before the applicable timed measurement phase starts.
4. The 3.0 V stability condition is a process-start condition only; voltage deviations during timed measurement are retained as raw data and do not automatically fail or terminate the benchmark.
5. `FULL_PACKAGE` records 3.00 V stable operation for 30 s, PWM +5 % relative to the original 3.00 V stable-drive PWM for 30 s, a 10 s 3.00 V return/buffer, PWM -5 % relative to the same original baseline PWM for 30 s, a 10 s 3.00 V return/buffer, and clear termination.
6. The two 10-second return phases are transition/buffer phases, not comparison windows.
7. Difficult-start motors can be recorded without imposing an evaluation judgment.
8. `FULL_PACKAGE` can also be used as the break-in / conditioning procedure, with purpose kept separate from benchmark type.
9. The selected benchmark mode is stored by the Library Manager / Measurement Session.
10. Raw time-series data remains the source of truth.
11. No unvalidated evaluation logic has been introduced.
12. The ±5 % change remains a provisional experimental condition subject to real-machine validation, not a final evaluation criterion.

Implementation is intentionally outside the scope of this specification. Any implementation or schema change should proceed only after Command Tower review/approval.
