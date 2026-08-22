# Battery Benchmark Specification v2

## Purpose

Battery Benchmark Result is the stable, analysis-ready summary derived from a completed discharge Measurement Session. Raw time-series Measurement data remains the source of truth.

## Required measurement data

Each valid measurement sample must retain elapsed time and the measured electrical values. The existing `measurement.elapsed_time` is the time axis for analysis.

Minimum analysis inputs:

- elapsed time (s)
- voltage
- current
- power when available
- measurement state

## Benchmark Result fields

The following fields are required or derived:

- `start_voltage`: first valid voltage in the actual discharge measurement interval
- `end_voltage`: last valid voltage in the actual discharge measurement interval
- `avg_voltage`: average voltage across valid measurement samples
- `avg_current`: average current across valid measurement samples
- `avg_power`: average power across valid measurement samples
- `max_current`: maximum measured current
- `max_power`: maximum measured power
- `discharge_time_s`: elapsed time from the first valid measurement to the last valid measurement
- `voltage_drop`: `start_voltage - end_voltage`
- `capacity_mah`: integrated current over elapsed time
- `energy_wh`: integrated power over elapsed time
- `measurement_count`: number of measurement samples used

## Rules

1. Start/end voltage are derived automatically from raw Measurement data; they are not manually entered.
2. Discharge time is derived from the Measurement elapsed-time axis; it is not manually entered.
3. `voltage_drop` is calculated from start/end voltage, not from max/min voltage.
4. A Benchmark Result is registered only for a completed discharge session.
5. STOP, CANCEL, or ERROR sessions are not eligible for formal Benchmark Result registration.
6. Raw Measurement data is preserved so the Analysis project can recompute additional metrics later.
7. Battery Analysis must consume Benchmark Result plus raw Measurement when a time-series analysis is required.
8. Battery-specific schema changes must not modify or delete shared Motor/Measurement data.

## Analysis handoff

The Battery Analysis project can rely on the following stable baseline:

`start_voltage`, `end_voltage`, `avg_voltage`, `voltage_drop`, `avg_current`, `max_current`, `avg_power`, `max_power`, `discharge_time_s`, `capacity_mah`, `energy_wh`, and the raw `elapsed_time` series.
