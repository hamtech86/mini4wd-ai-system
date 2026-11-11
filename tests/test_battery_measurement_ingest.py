import sqlite3

from measurement.battery_measurement_ingest import BatteryMeasurementIngestService


def _db():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.execute(
        """CREATE TABLE measurement_session (
            session_id TEXT PRIMARY KEY,
            measurement_type TEXT,
            status TEXT,
            start_time TEXT,
            end_time TEXT,
            measurement_count INTEGER,
            operator TEXT,
            notes TEXT,
            schema_version TEXT,
            firmware_version TEXT
        )"""
    )
    db.execute(
        """CREATE TABLE measurement (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT,
            record_type TEXT,
            device_model TEXT,
            instance_id TEXT,
            elapsed_time INTEGER,
            raw_acs1 INTEGER,
            raw_acs2 INTEGER,
            current1 REAL,
            current2 REAL,
            voltage1 REAL,
            voltage2 REAL,
            motor_voltage REAL,
            pwm INTEGER,
            direction TEXT,
            state TEXT,
            current_avg REAL,
            power REAL,
            current_ripple REAL,
            voltage_ripple REAL,
            peak_power REAL,
            peak_current REAL,
            peak_voltage REAL,
            peak_pwm INTEGER,
            brush_peak_current REAL,
            raw_magnetic INTEGER,
            magnetic_level REAL,
            motor_temperature REAL
        )"""
    )
    return db


def test_ingest_binds_measurement_to_existing_channel_session():
    db = _db()
    service = BatteryMeasurementIngestService(db)
    session = service.start_channel("CH1")

    measurement = service.ingest_frame(
        "DATA,BATTERY_DISCHARGER_V1,CH1,100,5.000,1.300,0,70,0,RUN",
        session.session_id,
    )

    row = db.execute("SELECT * FROM measurement").fetchone()
    assert row["session_id"] == session.session_id
    assert row["instance_id"] == "CH1"
    assert row["current1"] == 5.0
    assert measurement.session_id == session.session_id
    assert db.execute(
        "SELECT measurement_count FROM measurement_session WHERE session_id=?",
        (session.session_id,),
    ).fetchone()[0] == 1


def test_ingest_rejects_wrong_channel():
    db = _db()
    service = BatteryMeasurementIngestService(db)
    session = service.start_channel("CH1")

    try:
        service.ingest_frame(
            "DATA,BATTERY_DISCHARGER_V1,CH2,100,5.000,1.300,0,70,0,RUN",
            session.session_id,
        )
    except ValueError as exc:
        assert "channel" in str(exc)
    else:
        raise AssertionError("wrong channel was accepted")
