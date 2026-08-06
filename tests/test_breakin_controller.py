"""
MOTOR_BREAKIN_V3
Break-in Controller unit test

Hardware independent test using mock objects.
"""

from controlles.breakin_controller import BreakinController
from controlles.recipe import BreakinPhase, BreakinRecipe


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


class MockMeasurementManager:
    def collect(self):
        return {"measurement": "dummy"}


class MockAnalysisEngine:
    def analyze(self, measurement):
        return {"result": "dummy"}


def test_breakin_controller_phase_execution():
    serial = MockSerialController()
    measurement = MockMeasurementManager()

    controller = BreakinController(
        serial_controller=serial,
        measurement_manager=measurement,
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
    assert "FORWARD" in serial.commands
    assert "PWM:100" in serial.commands
    assert "STOP" in serial.commands


def test_emergency_stop():
    serial = MockSerialController()

    controller = BreakinController(
        serial_controller=serial,
    )

    controller.running = True
    controller.emergency_stop()

    assert controller.running is False
    assert "STOP" in serial.commands
