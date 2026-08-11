-- ============================================================
-- MINI4WD AI SYSTEM
-- Benchmark Result
-- ============================================================

CREATE TABLE IF NOT EXISTS benchmark_result (
    benchmark_id INTEGER PRIMARY KEY AUTOINCREMENT,
    instance_id TEXT NOT NULL,
    session_id TEXT NOT NULL UNIQUE,
    benchmark_rpm REAL NOT NULL,
    source TEXT NOT NULL DEFAULT 'USER_CONFIRMED',
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(session_id) REFERENCES measurement_session(session_id)
);

CREATE INDEX IF NOT EXISTS idx_benchmark_result_instance
    ON benchmark_result(instance_id);

CREATE INDEX IF NOT EXISTS idx_benchmark_result_session
    ON benchmark_result(session_id);
