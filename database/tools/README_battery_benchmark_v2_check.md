Battery Benchmark v2 E2E check

Run:

python3 database/tools/migrate_battery_benchmark_v2.py
python3 database/tools/verify_battery_benchmark_v2.py

PASS marker:
BATTERY_BENCHMARK_V2_E2E_PASS checked=N

The migration is additive and preserves raw Measurement data.