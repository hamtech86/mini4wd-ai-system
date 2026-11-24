import sqlite3
import pytest

from analysis.battery_benchmark_service import BatteryBenchmarkService


def make_database():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE measurement_session (session_id TEXT PRIMARY KEY, scope_key TEXT)")
    db.execute("""CREATE TABLE measurement (
        id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
        scope_key TEXT, elapsed_time REAL, voltage1 REAL, voltage2 REAL,
        current1 REAL, current2 REAL, power REAL
    )""")
    db.executemany(
        "INSERT INTO measurement_session(session_id,scope_key) VALUES (?,?)",
        [("S1", "BATTERY:CH1"), ("S2", "BATTERY:CH2")],
    )
    db.executemany(
        """INSERT INTO measurement(session_id,scope_key,elapsed_time,voltage1,voltage2,current1,current2)
           VALUES(?,?,?,?,?,?,?)""",
        [
            ("S1", "BATTERY:CH1", 0.0, 1.40, 1.42, 5.0, 4.8),
            ("S1", "BATTERY:CH1", 2.0, 1.38, 1.40, 5.0, 4.8),
            ("S2", "BATTERY:CH2", 0.0, 1.40, 1.42, 5.0, 4.8),
        ],
    )
    db.commit()
    return db


def test_service_reads_and_saves_only_the_requested_channel():
    db = make_database()
    before = db.execute("SELECT * FROM measurement ORDER BY id").fetchall()
    service = BatteryBenchmarkService(db)
    result1 = service.analyze_session("S1", channel="CH1")
    result2 = service.analyze_session("S2", channel="CH2")
    after = db.execute("SELECT * FROM measurement ORDER BY id").fetchall()
    assert result1["channel"] == "CH1" and result2["channel"] == "CH2"
    assert result1["avg_voltage"] != result2["avg_voltage"]
    assert before == after
    assert db.execute("SELECT COUNT(*) FROM battery_benchmark_result").fetchone()[0] == 2


def test_service_requires_explicit_channel():
    db = make_database()
    service = BatteryBenchmarkService.__new__(BatteryBenchmarkService)
    service.database = db
    with pytest.raises(TypeError):
        service.analyze_session("S1")


@pytest.mark.parametrize("requested_channel", ["CH1", "CH2"])
def test_service_rejects_session_scope_mismatch(requested_channel):
    db = make_database()
    service = BatteryBenchmarkService(db)
    with pytest.raises(ValueError, match="Session Scope Key"):
        service.analyze_session("S1", channel=requested_channel if requested_channel == "CH2" else "CH2")


@pytest.mark.parametrize("bad_scopes", [
    [None, "BATTERY:CH1"],
    ["BATTERY:CH1", "BATTERY:CH2"],
    ["UNKNOWN", "UNKNOWN"],
])
def test_service_rejects_missing_unknown_or_mixed_measurement_scopes(bad_scopes):
    db = make_database()
    db.execute("DELETE FROM measurement WHERE session_id='S1'")
    for index, scope in enumerate(bad_scopes):
        db.execute(
            "INSERT INTO measurement(session_id,scope_key,elapsed_time,voltage1,current1) VALUES(?,?,?,?,?)",
            ("S1", scope, float(index), 1.4, 5.0),
        )
    db.commit()
    service = BatteryBenchmarkService(db)
    with pytest.raises(ValueError, match="Measurement Scope Keys"):
        service.analyze_session("S1", channel="CH1")


def test_service_rejects_schema_without_persisted_scope_key():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE measurement_session (session_id TEXT PRIMARY KEY)")
    db.execute("CREATE TABLE measurement (id INTEGER PRIMARY KEY, session_id TEXT)")
    service = BatteryBenchmarkService.__new__(BatteryBenchmarkService)
    service.database = db
    with pytest.raises(ValueError, match="persisted Scope Key"):
        service.analyze_session("S1", channel="CH1")
