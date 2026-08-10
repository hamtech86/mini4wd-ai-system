from controllers.breakin_controller import BreakinController
from controllers.recipe import BreakinPhase, BreakinRecipe
from measurement.measurement import Measurement


class Serial:
    def forward(self):
        pass

    def reverse(self):
        pass

    def set_pwm(self, pwm):
        pass

    def stop_breakin(self):
        pass


class MeasurementManager:
    def collect(self):
        return Measurement(
            record_type="DATA",
            device_model="MOTOR_BREAKIN_V3",
            instance_id="000001",
            elapsed_time=0,
            raw_acs1=513,
            raw_acs2=513,
            current1=0.2,
            current2=0.1,
            voltage1=4.8,
            voltage2=0.1,
            motor_voltage=4.7,
            pwm=80,
            direction="FWD",
            state="RUN",
            current_avg=0.2,
            power=0.94,
            current_ripple=0.1,
            voltage_ripple=0.1,
            peak_power=1.0,
            peak_current=0.3,
            peak_voltage=4.8,
            peak_pwm=80,
            brush_peak_current=0.2,
            raw_magnetic=541,
            magnetic_level=2.64,
            motor_temperature=23.6,
        )


class Session:
    session_id = "test-session"


class SessionManager:
    def start(self, measurement_type, instance_id):
        assert measurement_type == "BREAKIN"
        assert instance_id == 1
        return Session()

    def finish(self, status):
        assert status == "COMPLETE"


class Repository:
    def __init__(self):
        self.saved = []

    def insert(self, measurement):
        self.saved.append(measurement)


class Analysis:
    def analyze(self, measurement):
        return {"result": "ok"}


def test_breakin_controller_persists_measurement():
    repository = Repository()
    controller = BreakinController(
        serial_controller=Serial(),
        measurement_manager=MeasurementManager(),
        analysis_engine=Analysis(),
        session_manager=SessionManager(),
        measurement_repository=repository,
    )

    recipe = BreakinRecipe(
        name="TEST_DB",
        phases=[BreakinPhase(name="PHASE1", duration_sec=0, pwm=80, direction="FWD")],
    )

    result = controller.start(recipe, instance_id=1)

    assert result == [{"result": "ok"}]
    assert len(repository.saved) == 1
    assert repository.saved[0].session_id == "test-session"
    assert repository.saved[0].instance_id == "1"
