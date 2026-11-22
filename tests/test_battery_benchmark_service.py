import sqlite3
import pytest

from analysis.battery_benchmark_service import BatteryBenchmarkService


def test_service_reads_and_saves_only_the_requested_channel():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE measurement_session (session_id TEXT PRIMARY KEY)")
    db.execute("""CREATE TABLE measurement (
        id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
        elapsed_time REAL, voltage1 REAL, voltage2 REAL,
        current1 REAL, current2 REAL, power REAL
    )""")
    db.execute("INSERT INTO measurement_session VALUES ('S1')")
    db.executemany(
        "INSERT INTO measurement(session_id,elapsed_time,voltage1,voltage2,current1,current2) VALUES(?,?,?,?,?,?)",
        [("S1", 0.0, 1.40, 1.42, 5.0, 4.8), ("S1", 2.0, 1.38, 1.40, 5.0, 4.8)],
    )
    db.commit()
    before = db.execute("SELECT * FROM measurement ORDER BY id").fetchall()
    service = BatteryBenchmarkService(db)
    result1 = service.analyze_session("S1", channel="CH1")
    result2 = service.analyze_session("S1", channel="CH2")
    after = db.execute("SELECT * FROM measurement ORDER BY id").fetchall()
    assert result1["channel"] == "CH1" and result2["channel"] == "CH2"
    assert result1["avg_voltage"] != result2["avg_voltage"]
    assert before == after
    assert db.execute("SELECT COUNT(*) FROM battery_benchmark_result").fetchone()[0] == 2


def test_service_requires_explicit_channel():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE measurement_session (session_id TEXT PRIMARY KEY)")
    service = BatteryBenchmarkService.__new__(BatteryBenchmarkService)
    service.database = db
    with pytest.raises(TypeError):
        service.analyze_session("S1")
