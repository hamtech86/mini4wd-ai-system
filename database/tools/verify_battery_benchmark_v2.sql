-- Manual SQL verification helper for Battery Benchmark v2.
-- Replace :session_id with a completed session_id if desired.
SELECT
    b.result_id,
    b.session_id,
    b.start_voltage,
    b.end_voltage,
    b.voltage_drop,
    (
        SELECT voltage1 FROM measurement m
        WHERE m.session_id = b.session_id AND m.voltage1 IS NOT NULL
        ORDER BY m.elapsed_time ASC LIMIT 1
    ) AS expected_start_voltage,
    (
        SELECT voltage1 FROM measurement m
        WHERE m.session_id = b.session_id AND m.voltage1 IS NOT NULL
        ORDER BY m.elapsed_time DESC LIMIT 1
    ) AS expected_end_voltage
FROM battery_benchmark_result b
WHERE (:session_id IS NULL OR b.session_id = :session_id)
ORDER BY b.result_id DESC;
