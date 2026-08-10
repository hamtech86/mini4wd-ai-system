from controllers.breakin_controller import BreakinController
from controllers.recipe import BreakinPhase, BreakinRecipe
from database.manager.database_manager import DatabaseManager
from database.repository.measurement_repository import MeasurementRepository
from database.repository.session_repository import SessionRepository
from measurement.measurement import Measurement
from measurement.measurement_session import MeasurementSession, MeasurementType


LEGACY_SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE motor_instance (
    instance_id INTEGER PRIMARY KEY
);

CREATE TABLE measurement_session (
    session_id INTEGER PRIMARY KEY,
    instance_id INTEGER NOT NULL,
    device_type TEXT NOT NULL,
    device_model TEXT,
    firmware_version TEXT,
    analysis_version TEXT,
    calibration_profile TEXT,
    start_datetime DATETIME,
    end_datetime DATETIME,
    operator TEXT,
    result TEXT,
    notes TEXT,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME,
    measurement_type TEXT NOT NULL DEFAULT 'BREAKIN',
    FOREIGN KEY(instance_id) REFERENCES motor_instance(instance_id)
);

CREATE TABLE measurement (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    record_type TEXT,
    device_model TEXT,
    instance_id TEXT,
    elapsed_time REAL,
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
);

INSERT INTO motor_instance(instance_id) VALUES (1);
"""


class MockSerialController:
    def forward(self):
        pass

    def reverse(self):
        pass

    def set_pwm(self, pwm):
        pass

    def stop_breakin(self):
        pass


class MockMeasurementManager:
    def collect(self):
        return Measurement(
            record_type="DATA",
            device_model="MOTOR_BREAKIN_V3",
            instance_id="000001",
            elapsed_time=0,
            raw_acs1=503,
            raw_acs2=508,
            current1=0.258,
            current2=0.124,
            voltage1=4.374,
            voltage2=0.724,
            motor_voltage=3.650,
            pwm=80,
            direction="FWD",
            state="RUN",
            current_avg=0.191,
            power=0.698,
            current_ripple=0.145,
            voltage_ripple=0.696,
            peak_power=0.0,
            peak_current=0.0,
            peak_voltage=0.0,
            peak_pwm=0,
            brush_peak_current=0.0,
            raw_magnetic=541,
            magnetic_level=2.639,
            motor_temperature=23.6,
        )


class MockAnalysisEngine:
    def analyze(self, measurement):
        return {"result": "OK", "session_id": measurement.session_id}


class DatabaseSessionManager:
    def __init__(self, session_repository, measurement_repository):
        self.session_repository = session_repository
        self.measurement_repository = measurement_repository
        self.session = None

    def start(self, measurement_type, instance_id):
        assert measurement_type == "BREAKIN"
        self.session = MeasurementSession(
            measurement_type=MeasurementType.BREAKIN,
            instance_id=instance_id,
        )
        self.session.start()
        self.session_repository.insert(self.session)
        return self.session

    def finish(self, status):
        self.session.measurement_count = self.measurement_repository.count_by_session(
            self.session.session_id
        )
        if status == "COMPLETE":
            self.session.finish()
        elif status == "ERROR":
            self.session.error()
        else:
            self.session.cancel()
        self.session_repository.update(self.session)


def test_complete_breakin_persists_session_and_measurement(tmp_path):
    db = DatabaseManager(str(tmp_path / "mini4wd.db"))
    db.connect()
    db.executescript(LEGACY_SCHEMA)

    measurement_repository = MeasurementRepository(db)
    session_repository = SessionRepository(db)
    session_manager = DatabaseSessionManager(
        session_repository,
        measurement_repository,
    )

    controller = BreakinController(
        serial_controller=MockSerialController(),
        measurement_manager=MockMeasurementManager(),
        analysis_engine=MockAnalysisEngine(),
        session_manager=session_manager,
        measurement_repository=measurement_repository,
    )

    recipe = BreakinRecipe(
        name="DB_TEST",
        phases=[
            BreakinPhase(
                name="PHASE1",
                duration_sec=0,
                pwm=80,
                direction="FWD",
            )
        ],
    )

    result = controller.start(recipe, instance_id=1)
    db.commit()

    session_id = session_manager.session.session_id
    session_row = session_repository.find(session_id)

    assert len(result) == 1
    assert result[0]["result"] == "OK"
    assert result[0]["session_id"] == session_id
    assert measurement_repository.count_by_session(session_id) == 1
    assert session_row["instance_id"] == 1
    assert session_row["result"] == "COMPLETE"
    assert session_row["measurement_type"] == "BREAKIN"

    db.close()
