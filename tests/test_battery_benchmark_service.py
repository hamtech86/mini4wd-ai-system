import sqlite3

from analysis.battery_benchmark_service import BatteryBenchmarkService


def test_service_reads_measurement_and_only_writes_result():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute(
        "CREATE TABLE measurement_session (session_id TEXT PRIMARY KEY)"
    )
    db.execute(
        """CREATE TABLE measurement (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            elapsed_time REAL,
            voltage1 REAL,
            voltage2 REAL,
            current1 REAL,
            current2 REAL,
            power REAL
        )"""
    )
    db.execute("INSERT INTO measurement_session VALUES ('S1')")
    db.executemany(
        "INSERT INTO measurement(session_id,elapsed_time,voltage1,current1) VALUES(?,?,?,?)",
        [('S1', 0.0, 1.40, 5.0), ('S1', 2.0, 1.38, 5.0)],
    )
    db.commit()

    before = db.execute("SELECT * FROM measurement ORDER BY id").fetchall()
    result = BatteryBenchmarkService(db).analyze_session('S1')
    after = db.execute("SELECT * FROM measurement ORDER BY id").fetchall()

    assert result['measurement_count'] == 2
    assert result['capacity_mah'] == 10.0 / 3600.0 * 1000.0
    assert before == after
    assert db.execute("SELECT COUNT(*) FROM battery_benchmark_result").fetchone()[0] == 1
