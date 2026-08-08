"""
MINI4WD AI SYSTEM
Break-in Controller Integration Test

Verify:
Recipe
 -> BreakinController
 -> Measurement
 -> AnalysisEngine
"""

from controllers.breakin_controller import BreakinController
from controllers.recipe import BreakinRecipe, BreakinPhase


class MockSerial:
    def __init__(self):
        self.commands = []

    def forward(self):
        self.commands.append("FWD")

    def reverse(self):
        self.commands.append("REV")

    def set_pwm(self, pwm):
        self.commands.append(("PWM", pwm))

    def stop_breakin(self):
        self.commands.append("STOP")


class MockMeasurementManager:
    def collect(self):
        return {
            "voltage": 3.0,
            "current": 0.5,
            "rpm": 10000,
        }


class MockAnalysisEngine:
    def analyze(self, measurement):
        return {
            "status": "OK",
            "measurement": measurement,
        }


def test_breakin_controller_flow():
    serial = MockSerial()

    controller = BreakinController(
        serial_controller=serial,
        measurement_manager=MockMeasurementManager(),
        analysis_engine=MockAnalysisEngine(),
    )

    recipe = BreakinRecipe(
        name="TEST",
        phases=[
            BreakinPhase(
                name="START",
                duration_sec=0,
                pwm=100,
                direction="FWD",
            )
        ],
    )

    result = controller.start(recipe)

    assert len(result) == 1
    assert "FWD" in serial.commands
    assert ("PWM", 100) in serial.commands
    assert "STOP" in serial.commands
