import sqlite3

from database.repository.measurement_repository import MeasurementRepository
from measurement.measurement import Measurement


class SQLiteDatabase:
    def __init__(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.execute("""
            CREATE TABLE measurement (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                record_type TEXT, device_model TEXT, instance_id TEXT,
                elapsed_time REAL, raw_acs1 INTEGER, raw_acs2 INTEGER,
                current1 REAL, current2 REAL, voltage1 REAL, voltage2 REAL,
                motor_voltage REAL, pwm INTEGER, direction TEXT, state TEXT,
                current_avg REAL, power REAL, current_ripple REAL,
                voltage_ripple REAL, peak_power REAL, peak_current REAL,
                peak_voltage REAL, peak_pwm INTEGER, brush_peak_current REAL,
                raw_magnetic INTEGER, magnetic_level REAL, motor_temperature REAL
            )
        """)

    def execute(self, sql, params=()):
        cursor = self.connection.execute(sql, params)
        self.connection.commit()
        return cursor


def make_measurement():
    return Measurement(
        record_type="DATA",
        device_model="MOTOR_BREAKIN_V3",
        instance_id="000001",
        elapsed_time=100,
        raw_acs1=503,
        raw_acs2=507,
        current1=0.25,
        current2=0.15,
        voltage1=4.8,
        voltage2=0.3,
        motor_voltage=4.5,
        pwm=80,
        direction="FWD",
        state="RUN",
        current_avg=0.2,
        power=0.9,
        current_ripple=0.1,
        voltage_ripple=0.1,
        peak_power=1.0,
        peak_current=0.3,
        peak_voltage=4.8,
        peak_pwm=80,
        brush_peak_current=0.2,
        raw_magnetic=0,
        magnetic_level=0.0,
        motor_temperature=23.6,
        session_id="test-session",
    )


def test_measurement_repository_insert_and_count():
    db = SQLiteDatabase()
    repository = MeasurementRepository(db)

    repository.insert(make_measurement())

    assert repository.count_by_session("test-session") == 1
