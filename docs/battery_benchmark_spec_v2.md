# Battery Benchmark Specification v2

## Purpose

Battery Benchmark Result is the stable, analysis-ready summary derived from a completed discharge Measurement Session. Raw time-series Measurement data remains the source of truth.

## Required measurement data

Each valid measurement sample must retain elapsed time and measured electrical values. The existing `measurement.elapsed_time` is the time axis for analysis.

Minimum analysis inputs:

- elapsed time (s)
- voltage (CH1 or CH2)
- current
- power when available
- measurement state

## Benchmark Result fields

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
2. Start/end voltage derivation supports independent CH1 and CH2 sessions by using the populated voltage channel.
3. Discharge time is derived from the Measurement elapsed-time axis; it is not manually entered.
4. `voltage_drop` is calculated from start/end voltage, not max/min voltage.
5. A Benchmark Result is registered only for a completed discharge session.
6. STOP, CANCEL, or ERROR sessions are not eligible for formal Benchmark Result registration.
7. Raw Measurement data is preserved so Analysis can recompute additional metrics later.
8. Battery-specific schema changes must not modify or delete shared Motor/Measurement data.

## E2E acceptance criterion

The feature is considered complete only when an existing real Measurement session is used to populate `start_voltage`, `end_voltage`, and `voltage_drop` in `battery_benchmark_result`, and the stored values are verified against the raw Measurement rows.
