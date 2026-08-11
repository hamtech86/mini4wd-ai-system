# Benchmark Result Persistence Boundary

The Instance Manager accepts a confirmed benchmark result as a separate result value.

## Contract

```text
instance_id + session_id + benchmark_rpm(optional)
```

## Rules

1. `instance_id` and `session_id` are mandatory.
2. `benchmark_rpm` may be omitted; omission means unavailable, not zero.
3. `benchmark_rpm` must be positive when supplied.
4. Raw `breakin_log.measured_rpm` is never overwritten.
5. The persistence implementation may map this contract to the project's final result/analysis schema once that schema is finalized by the architecture owner.

This file intentionally avoids adding an unapproved database column. The existing database schema remains authoritative until the architecture owner approves the final storage location for the separate benchmark result.
