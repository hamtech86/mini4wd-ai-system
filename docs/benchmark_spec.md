# Motor Benchmark Specification

## Purpose

The benchmark produces a reproducible raw measurement record. The raw log is the only source used for AI analysis. UI-derived averages, scores, and voltage-converted values are presentation aids only and are not AI inputs.

## Start condition

A benchmark does not start merely because the command voltage reaches 3.0 V.

After the 3.0 V command is applied, the controller enters `STABILIZING`. The motor must demonstrate that it has started and reached a measurable operating state. The initial implementation uses the following conservative criteria:

- measured motor voltage >= 1.5 V
- measured motor current >= 0.05 A
- both conditions remain true for 500 ms
- no excessive voltage instability during that confirmation interval

The 1.5 V value is an empirical starting threshold based on observed magnetized motors. It is a configurable benchmark parameter and should be validated against real logs before being treated as a permanent physical limit.

If the motor does not satisfy the start condition within the configured startup timeout, the benchmark is aborted rather than producing a misleading 30-second result.

The instant the start condition is confirmed is `BENCHMARK_START` / elapsed time zero.

## Formal measurement

- Formal measurement duration: 30 s
- Only samples collected after `BENCHMARK_START` belong to the formal benchmark dataset.
- Stabilization samples are not included in the AI RAW LOG.
- Break-in samples are not included in the AI RAW LOG.
- A motor that cannot maintain the commanded 3.0 V is not automatically rejected. Its actual measured voltage is retained as raw data.

## Result display

The UI must display the arithmetic mean of the measured motor voltage during the 30-second formal measurement as `Measurement Average Voltage`.

The UI may also display user-facing reference estimates for:

- 3.0 V equivalent
- 2.8 V equivalent

These are convenience/reference values for the operator. They are not authoritative measurements and must not be substituted for the raw log in AI analysis.

## AI analysis boundary

AI analysis consumes raw benchmark samples only. It must not depend on:

- average voltage
- average current
- benchmark score
- 3.0 V conversion
- 2.8 V conversion
- previous AI analysis results

This preserves the original measurement and allows definitions, analysis methods, and conversion models to be updated and re-run against historical data.
