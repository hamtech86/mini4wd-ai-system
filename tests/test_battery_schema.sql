-- Structural smoke checks for the additive Battery benchmark schema.
-- Executed by the project's DB test harness when available.
SELECT name FROM sqlite_master WHERE type='table' AND name IN ('battery_model','battery_instance','battery_benchmark_result');
