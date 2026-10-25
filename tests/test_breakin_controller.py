"""
MOTOR_BREAKIN_V3
Break-in Controller integration test

Hardware-independent verification of the complete controller path.
"""

import pytest

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

    def analyze(self, measurement):
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



def test_emergency_stop_attempts_serial_even_if_checkpoint_save_fails():
    serial = MockSerialController()
    controller = BreakinController(serial_controller=serial)
    controller.running = True

    def fail_checkpoint():
        raise OSError("checkpoint unavailable")

    controller._save_checkpoint = fail_checkpoint
    result = controller.emergency_stop()

    assert controller.running is False
    assert "EMERGENCY_STOP" in serial.commands
    assert result["checkpoint_saved"] is False
    assert result["serial_stop_attempted"] is True
    assert any("checkpoint unavailable" in error for error in result["errors"])



def test_emergency_stop_clears_checkpoint_to_prevent_resume(monkeypatch, tmp_path):
    serial = MockSerialController()
    controller = BreakinController(serial_controller=serial)
    checkpoint = tmp_path / "breakin_resume.json"
    monkeypatch.setattr(BreakinController, "CHECKPOINT_PATH", checkpoint)

    def save_checkpoint():
        checkpoint.write_text('{"recipe": "TUNE_BASIC"}', encoding="utf-8")

    controller._save_checkpoint = save_checkpoint
    controller.emergency_stop()

    assert not checkpoint.exists()



def test_controller_latch_blocks_direct_restart_after_emergency_stop():
    controller = BreakinController(serial_controller=MockSerialController())
    controller.emergency_stop()
    recipe = BreakinRecipe(
        name="TEST",
        phases=[BreakinPhase(name="PHASE1", duration_sec=0, pwm=0, direction="FWD")],
    )

    with pytest.raises(RuntimeError, match="Emergency STOP latch is active"):
        controller.start(recipe)

def test_emergency_stop_attempts_serial_before_checkpoint_io():
    events = []

    class OrderedSerial:
        def emergency_stop(self):
            events.append("serial_stop")
            return {"pwm_zero": True, "stop_command": True, "disconnect": True, "errors": []}

    controller = BreakinController(serial_controller=OrderedSerial())
    controller._save_checkpoint = lambda: events.append("checkpoint_save")
    controller.clear_checkpoint = lambda: events.append("checkpoint_clear")

    controller.emergency_stop()

    assert events == ["serial_stop", "checkpoint_save", "checkpoint_clear"]



def test_repeated_emergency_stop_preserves_first_attempt_and_does_not_retry():
    class CountingSerial:
        def __init__(self):
            self.calls = 0

        def emergency_stop(self):
            self.calls += 1
            return {
                "pwm_zero": False,
                "stop_command": False,
                "disconnect": True,
                "errors": ["serial write failed"],
            }

    serial = CountingSerial()
    controller = BreakinController(serial_controller=serial)

    first = controller.emergency_stop()
    second = controller.emergency_stop()

    assert serial.calls == 1
    assert second is first
    assert second["serial_result"]["pwm_zero"] is False
    assert second["serial_result"]["stop_command"] is False
    assert second["serial_result"]["errors"] == ["serial write failed"]



def test_emergency_stop_preserves_interrupted_phase_raw_log_after_stop_attempt():
    events = []

    class RawLogSerial:
        def emergency_stop(self):
            events.append("stop")
            return {"pwm_zero": True, "stop_command": True, "disconnect": True, "errors": []}

        def freeze_raw_log(self):
            events.append("freeze")
            return "DATA,interrupted-phase\\n"

    controller = BreakinController(serial_controller=RawLogSerial())
    controller.running = True

    controller.emergency_stop()

    assert events[:2] == ["stop", "freeze"]
    assert controller.measurement_raw_log == "DATA,interrupted-phase\\n"
