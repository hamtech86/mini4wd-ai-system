"""
MOTOR_BREAKIN_V3
Break-in Controller integration test

Hardware-independent verification of the complete controller path.
"""

from controllers.breakin_controller import BreakinController
from controllers.recipe import BreakinPhase, BreakinRecipe


class MockSerialController:
    def __init__(self):
        self.commands = []

    def forward(self):
        self.commands.append("FORWARD")

    def reverse(self):
        self.commands.append("REVERSE")

    def set_pwm(self, pwm):
        self.commands.append(f"PWM:{pwm}")

    def stop_breakin(self):
        self.commands.append("STOP")

    def emergency_stop(self):
        self.commands.append("EMERGENCY_STOP")


class MockMeasurementManager:
    def __init__(self):
        self.count = 0

    def collect(self):
        self.count += 1
        return {"measurement": "dummy", "sample": self.count}


class MockAnalysisEngine:
    def __init__(self):
        self.measurements = []

    def analyze(self, measurement, motor_model=None):
        self.measurements.append(measurement)
        return {"result": "dummy", "sample": measurement["sample"]}


def test_complete_breakin_controller_path():
    serial = MockSerialController()
    measurement = MockMeasurementManager()
    analysis = MockAnalysisEngine()

    controller = BreakinController(
        serial_controller=serial,
        measurement_manager=measurement,
        analysis_engine=analysis,
    )

    recipe = BreakinRecipe(
        name="TEST",
        phases=[
            BreakinPhase(
                name="PHASE1",
                duration_sec=0,
                pwm=100,
                direction="FWD",
            )
        ],
    )

    result = controller.start(recipe)

    assert len(result) == 1
    assert result[0]["result"] == "dummy"
    assert len(analysis.measurements) == 1
    assert "FORWARD" in serial.commands
    assert "PWM:100" in serial.commands
    assert "STOP" in serial.commands


def test_emergency_stop():
    serial = MockSerialController()

    controller = BreakinController(serial_controller=serial)
    controller.running = True

    controller.emergency_stop()

    assert controller.running is False
    assert "EMERGENCY_STOP" in serial.commands
