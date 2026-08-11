# Benchmark RPM Handoff Contract

## Purpose

Define the interface between Main.py (break-in/benchmark) and Motor Instance Manager.

## Ownership

- Main.py owns benchmark execution and user entry of the benchmark RPM.
- Instance Manager owns storage/display/comparison of the benchmark result.
- Neither side changes the other side's internal implementation.

## Required identifiers

Every stored benchmark result must be associated with:

- `instance_id`: Motor Instance ID
- `session_id`: Measurement Session ID
- `benchmark_rpm`: RPM value confirmed by the user

## Measurement rule

`breakin_log.measured_rpm` remains the raw/application measurement and must not be overwritten by a manually confirmed benchmark RPM.

The benchmark RPM is a separate result-level value.

## UI rule

Main.py should place the optional RPM input in the Benchmark Result/finalization area, after the application-measured RPM is shown.

Suggested labels:

- Application RPM: read-only measured value
- Benchmark RPM: editable optional value
- Save/Confirm Benchmark RPM

## Instance Manager rule

The Instance Manager should expose the confirmed benchmark RPM in:

1. Motor Instance detail
2. Measurement/benchmark history
3. Multi-instance comparison

A missing benchmark RPM is valid and must be displayed as unavailable rather than treated as zero.

## Future compatibility

The storage field should remain distinct from raw break-in measurements so later analysis can compare application measurement, externally confirmed benchmark measurement, and derived analysis results without modifying historical raw data.
