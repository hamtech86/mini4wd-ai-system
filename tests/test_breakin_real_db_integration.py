from pathlib import Path

from controllers.breakin_controller import BreakinController
from controllers.recipe import BreakinPhase, BreakinRecipe
from database.manager.database_manager import DatabaseManager
from database.repository.measurement_repository import MeasurementRepository
from database.repository.session_repository import SessionRepository
from measurement.measurement import Measurement
from measurement.measurement_session import MeasurementSession, MeasurementType


SCHEMA = Path("database/schema/create_tables.sql").read_text(encoding="utf-8")


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

    def start(self, measurement_type):
        self.session = MeasurementSession(
            measurement_type=MeasurementType.BREAKIN
        )
        self.session.start()
        self.session_repository.insert(self.session)
        return self.session

    def finish(self, status):
        self.session.measurement_count = self.measurement_repository.count_by_session(
            self.session.session_id
        )
        self.session.finish()
        self.session_repository.update(self.session)


def test_complete_breakin_persists_session_and_measurement(tmp_path):
    db = DatabaseManager(str(tmp_path / "mini4wd.db"))
    db.connect()
    db.executescript(SCHEMA)

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

    result = controller.start(recipe)
    db.commit()

    session_id = session_manager.session.session_id
    session_row = session_repository.find(session_id)

    assert len(result) == 1
    assert result[0]["result"] == "OK"
    assert result[0]["session_id"] == session_id
    assert measurement_repository.count_by_session(session_id) == 1
    assert session_row["status"] == "FINISHED"
    assert session_row["measurement_count"] == 1
    assert session_row["measurement_type"] == "BREAKIN"

    db.close()
