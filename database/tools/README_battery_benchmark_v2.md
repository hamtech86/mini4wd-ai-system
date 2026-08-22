# Battery Benchmark v2 verification

Run from the repository root:

```bash
python3 database/tools/migrate_battery_benchmark_v2.py
python3 database/tools/verify_battery_benchmark_v2.py
```

The migration is additive and does not delete or rewrite raw Measurement rows.
It installs the automatic Benchmark Result derivation and backfills existing
Benchmark Result rows when linked raw Measurement data exists.

Expected verification output contains:

`BATTERY_BENCHMARK_V2_E2E_PASS checked=N`

A non-zero exit code means the existing database is not yet suitable to mark
this handoff as E2E verified.
