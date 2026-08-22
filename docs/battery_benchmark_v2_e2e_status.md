# Battery Benchmark v2 E2E Status

Implementation status:

- Raw Measurement remains source of truth.
- Benchmark Result contains `start_voltage`, `end_voltage`, and `voltage_drop`.
- Existing Benchmark Result rows can be backfilled from raw Measurement.
- New Benchmark Result inserts derive start/end/drop automatically.
- CH1 and CH2 independent sessions are supported via `COALESCE(voltage1, voltage2)`.
- Verification compares stored values against the first/last valid raw Measurement voltage.

The remaining acceptance step is execution against the user's real local `database/mini4wd.db` and confirmation of `BATTERY_BENCHMARK_V2_E2E_PASS`.
