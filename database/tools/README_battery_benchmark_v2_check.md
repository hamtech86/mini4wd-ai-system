Battery Benchmark v2 E2E check

Run from the repository root with an explicitly selected existing database (absolute path):

```bash
python3 -m database.tools.migrate_battery_benchmark_v2 --db /absolute/path/to/existing.db
python3 -m database.tools.verify_battery_benchmark_v2 --db /absolute/path/to/existing.db
```

Alternatively, set `MINI4WD_DB_PATH` to an absolute path to an existing database. Do not point it at an operational database without explicit approval. Migration is a write operation; verification opens the database read-only.

PASS marker: `BATTERY_BENCHMARK_V2_E2E_PASS checked=N`

The migration is additive and preserves raw Measurement data.
