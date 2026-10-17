# Battery Benchmark v2 verification

Run from the repository root and explicitly identify an existing database. The path must be absolute; neither command creates a missing database.

```bash
python3 -m database.tools.migrate_battery_benchmark_v2 --db /absolute/path/to/existing.db
python3 -m database.tools.verify_battery_benchmark_v2 --db /absolute/path/to/existing.db
```

Alternatively, set `MINI4WD_DB_PATH` to an absolute path of an existing database and omit `--db`. Do not set this variable to an operational database unless the Commander has explicitly approved that target and the specific migration.

The migration is additive and does not delete or rewrite raw Measurement rows. It installs the automatic Benchmark Result derivation and backfills existing Benchmark Result rows when linked raw Measurement data exists.

Expected verification output contains:

`BATTERY_BENCHMARK_V2_E2E_PASS checked=N`

A non-zero exit code means the selected database is not suitable to mark this handoff as E2E verified. The migration itself is a write operation and must only be run as a separately approved management action.
