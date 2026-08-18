import sqlite3

from analysis.battery_benchmark_service import BatteryBenchmarkService
from database.manager.database_manager import DatabaseManager
from measurement.battery_session_importer import BatterySessionImporter


def make_db():
    db = DatabaseManager(":memory:")
    db.connect()
    db.execute(
        """CREATE TABLE measurement_session (
            session_id TEXT PRIMARY KEY, measurement_type TEXT NOT NULL,
            status TEXT NOT NULL, start_time TEXT, end_time TEXT,
            measurement_count INTEGER DEFAULT 0, operator TEXT,
            notes TEXT, schema_version TEXT, firmware_version TEXT)"""
    )
    db.execute(
        """CREATE TABLE measurement (
            id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
            record_type TEXT, device_model TEXT, instance_id TEXT,
            elapsed_time REAL, raw_acs1 INTEGER, raw_acs2 INTEGER,
            current1 REAL, current2 REAL, voltage1 REAL, voltage2 REAL,
            motor_voltage REAL, pwm INTEGER, direction TEXT, state TEXT,
            current_avg REAL, power REAL, current_ripple REAL, voltage_ripple REAL,
            peak_power REAL, peak_current REAL, peak_voltage REAL, peak_pwm INTEGER,
            brush_peak_current REAL, raw_magnetic INTEGER, magnetic_level REAL,
            motor_temperature REAL, firmware_version TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(session_id) REFERENCES measurement_session(session_id))"""
    )
    db.commit()
    return db


def test_frames_become_independent_session_measurements_and_benchmarks():
    db = make_db()
    importer = BatterySessionImporter(db)
    ch1 = importer.start_session("CH1")
    ch2 = importer.start_session("CH2")

    importer.import_frames(ch1, [
        "DATA,BATTERY_DISCHARGER_V1,CH1,0,5.0,1.40,0,70,0,RUN",
        "DATA,BATTERY_DISCHARGER_V1,CH1,1000,5.0,1.30,0,70,0,RUN",
    ])
    importer.import_frames(ch2, [
        "DATA,BATTERY_DISCHARGER_V1,CH2,0,5.1,1.39,0,71,0,RUN",
        "DATA,BATTERY_DISCHARGER_V1,CH2,1000,5.1,1.29,0,71,0,RUN",
    ])

    assert db.execute("SELECT COUNT(*) FROM measurement WHERE session_id=?", (ch1.session_id,)).fetchone()[0] == 2
    assert db.execute("SELECT COUNT(*) FROM measurement WHERE session_id=?", (ch2.session_id,)).fetchone()[0] == 2

    # The CH2 result must use its actual voltage/current, not the inactive CH1=0 fields.
    result = BatteryBenchmarkService(db).analyze_session(ch2.session_id)
    assert result["avg_voltage"] == 1.34
    assert result["avg_current"] == 5.1
    assert result["capacity_mah"] == 5.1 / 3600.0 * 1000.0
    assert result["internal_resistance_mohm"] is None
