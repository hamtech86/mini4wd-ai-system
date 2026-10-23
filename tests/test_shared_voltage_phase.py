from types import SimpleNamespace

from controllers.timed_voltage_phase import run_timed_voltage_phase


class FakeController:
    CONTROL_INTERVAL_SEC = 0.0

    def __init__(self, safety=None):
        self.running = True
        self.paused = False
        self.phase_started_at = None
        self.phase_elapsed_before_pause = 0.0
        self.abort_reason = None
        self.events = []
        self.iterations = 0
        self.safety = safety

    def _effective_elapsed(self):
        self.iterations += 1
        return float(self.iterations)

    def _collect_measurement(self, phase):
        self.events.append("collect")
        return {"voltage": 3.0}

    def _safety_violation(self, measurement):
        self.events.append("safety")
        return self.safety

    def _voltage_control(self, phase, measurement):
        self.events.append("control")

    def _save_checkpoint(self):
        self.events.append("checkpoint")

    def emergency_stop(self):
        self.events.append("stop")
        self.running = False


def test_shared_voltage_runner_uses_safety_before_feedback_control():
    controller = FakeController()
    phase = SimpleNamespace(name="STD-I", target_voltage=3.0)

    assert run_timed_voltage_phase(controller, phase, 2.0) is True
    assert controller.events[:3] == ["collect", "safety", "control"]


def test_shared_voltage_runner_stops_before_control_when_safety_fails():
    controller = FakeController(safety="over-current")
    phase = SimpleNamespace(name="TuneBasic Phase 1", target_voltage=3.0)

    assert run_timed_voltage_phase(controller, phase, 2.0) is False
    assert controller.events == ["collect", "safety", "stop"]


def test_shared_voltage_runner_checkpoints_tunebasic_iterations():
    controller = FakeController()
    phase = SimpleNamespace(name="TuneBasic Phase 1", target_voltage=3.0)

    assert run_timed_voltage_phase(
        controller, phase, 2.0, save_checkpoint=True, initial_elapsed=4.0
    ) is True
    assert controller.phase_elapsed_before_pause == 4.0
    assert "checkpoint" in controller.events
