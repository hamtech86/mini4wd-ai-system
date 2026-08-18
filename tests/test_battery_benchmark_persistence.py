import sqlite3
from analysis.battery_benchmark_service import BatteryBenchmarkService


def test_benchmark_result_persists_without_mutating_measurement():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE measurement_session (session_id TEXT PRIMARY KEY)")
    db.execute("CREATE TABLE measurement (id INTEGER PRIMARY KEY, session_id TEXT, elapsed_time REAL, current1 REAL, current2 REAL, voltage1 REAL, voltage2 REAL, power REAL)")
    db.execute("INSERT INTO measurement_session VALUES ('S1')")
    db.executemany("INSERT INTO measurement VALUES (?,?,?,?,?,?,?,?)", [
        (1,'S1',0,5.0,0,1.4,0,7.0), (2,'S1',1000,5.0,0,1.3,0,6.5)])
    before = [tuple(r) for r in db.execute("SELECT * FROM measurement ORDER BY id")]
    result = BatteryBenchmarkService(db).analyze_session('S1', 'BAT-001')
    after = [tuple(r) for r in db.execute("SELECT * FROM measurement ORDER BY id")]
    stored = db.execute("SELECT * FROM battery_benchmark_result WHERE session_id='S1'").fetchone()
    assert before == after
    assert result['session_id'] == 'S1'
    assert result['instance_id'] == 'BAT-001'
    assert stored is not None
    assert stored['measurement_count'] == 2
