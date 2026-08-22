# Battery Benchmark Specification v2

Battery Benchmark Result is the analysis-ready summary of a completed discharge Measurement Session. Raw time-series Measurement remains the source of truth.

## Required fields

- `start_voltage`: first valid voltage in the discharge measurement interval
- `end_voltage`: last valid voltage in the discharge measurement interval
- `avg_voltage`
- `avg_current`
- `avg_power`
- `max_current`
- `max_power`
- `discharge_time_s`: elapsed time from first to last valid measurement
- `voltage_drop`: `start_voltage - end_voltage`
- `capacity_mah`
- `energy_wh`
- `measurement_count`

## Derivation rules

1. Start/end voltage are derived automatically from raw Measurement data.
2. CH1 and CH2 are supported independently. The populated voltage channel (`voltage1` or `voltage2`) is used.
3. Discharge time is derived from `measurement.elapsed_time`.
4. Voltage drop is calculated only from start/end voltage, never max/min voltage.
5. Raw Measurement data is never deleted by Benchmark processing.
6. Only COMPLETE sessions are eligible for formal Benchmark Result registration.

## E2E acceptance criterion

Completion requires an existing real Measurement session to populate `start_voltage`, `end_voltage`, and `voltage_drop` in `battery_benchmark_result`, followed by verification against the raw Measurement rows.
