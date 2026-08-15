# Benchmark / Motor Instance Linkage

## Purpose

A break-in benchmark must remain traceable from the selected Motor Instance through the measurement session and raw Measurement data to the final Analysis Result.

## Required chain

```text
Selected Motor Instance
        |
        v
Measurement Session
        |
        v
Arduino DATA record
        |
        v
Measurement
  - instance_id
  - session_id
  - voltage1
  - voltage2
  - motor_voltage
        |
        v
Analysis Result
```

## Current implementation observations

`Measurement` retains both `instance_id` and `session_id`. `MeasurementBuilder` copies both fields from the parsed Arduino DATA record, so the identifiers are not discarded at the communication boundary.

The firmware voltage fields are represented separately as `voltage1` and `voltage2`, with `motor_voltage` representing their difference. Therefore a negative LIVE voltage is currently a signed A4-A5 difference, not automatically proof of a faulty sensor.

## Benchmark note

The current RPM analysis contains a fallback estimate based on average voltage when a measured RPM value is unavailable. That value must not be presented as a measured RPM. Benchmark validation should therefore distinguish:

- raw/live sensor values;
- measured RPM, when an actual RPM sensor measurement exists;
- estimated RPM, when analysis fallback is used.

For the current bench test, smartphone RPM is the external benchmark reference. The observed approximately 28,000 rpm run should be retained as a benchmark observation rather than silently replacing the raw Measurement value.

## Next integration requirement

The UI should expose the active Motor Instance ID during LIVE SENSOR / break-in operation so the operator can verify that the physical motor being tested is the same instance associated with the resulting session and Measurement records.
