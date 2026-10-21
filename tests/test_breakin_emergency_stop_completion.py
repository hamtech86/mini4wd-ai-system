import pytest

from controllers.breakin_controller import BreakinController
from controllers.recipe import BreakinPhase, BreakinRecipe


class FakeSerial:
    def __init__(self):
        self.stop_calls = 0

    def arm(self):
        return True

    def emergency_stop(self):
        self.stop_calls += 1
        return {"pwm_zero": True, "stop_command": True, "disconnect": True, "errors": []}

    def set_pwm(self, value):
        return True

    def forward(self):
        return True

    def reverse(self):
        return True


def _recipe():
    return BreakinRecipe(
        name="STOP_RACE_TEST",
        description="Regression test for STOP at a phase boundary",
        brush="UNKNOWN",
        family="TEST",
        objective="TEST",
        phases=[BreakinPhase(
            name="PHASE_1", duration_sec=1.0, pwm=60, direction="FWD",
            control="PWM", target_voltage=None, pwm_min=0, pwm_max=120,
        )],
        target_rpm=None,
        torque_priority=0.5,
        version="test",
    )


@pytest.mark.parametrize("stop_boundary", ["during_phase", "phase_completion"])
def test_emergency_stop_never_returns_a_successfully_completed_recipe(monkeypatch, stop_boundary):
    serial = FakeSerial()
    controller = BreakinController(serial_controller=serial)
    # Prevent this unit test from touching the user's checkpoint file.
    monkeypatch.setattr(controller, "_save_checkpoint", lambda: None)
    monkeypatch.setattr(controller, "clear_checkpoint", lambda: None)

    def stop_at_boundary(phase, resume_elapsed=0.0):
        controller.current_phase = phase
        if stop_boundary == "during_phase":
            controller.emergency_stop()
            return
        # Simulate STOP arriving at the last boundary before execute_phase()
        # returns to start() and advances/finalizes the recipe.
        controller.emergency_stop()

    monkeypatch.setattr(controller, "execute_phase", stop_at_boundary)

    with pytest.raises(RuntimeError, match="Emergency STOP interrupted the active recipe; result is incomplete"):
        controller.start(_recipe())

    assert controller.emergency_stop_latched is True
    assert controller.running is False
    assert serial.stop_calls >= 1
