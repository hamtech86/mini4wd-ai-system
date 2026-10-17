import time

from controllers.breakin_controller import BreakinController
from controllers.recipe import BreakinPhase


class FakeSerial:
    def __init__(self):
        self.commands = []

    def set_pwm(self, pwm):
        self.commands.append(pwm)


def test_remaining_time_is_provided_by_active_controller_phase():
    controller = BreakinController(FakeSerial())
    controller.current_phase = BreakinPhase("timed", duration_sec=10, pwm=80)
    controller.phase_elapsed_before_pause = 0.0
    controller.phase_started_at = time.time() - 4.0
    assert 5.8 <= controller.remaining_sec() <= 6.0


def test_remaining_time_is_frozen_while_paused():
    controller = BreakinController(FakeSerial())
    controller.current_phase = BreakinPhase("timed", duration_sec=10, pwm=80)
    controller.phase_elapsed_before_pause = 4.0
    controller.phase_started_at = time.time() - 9.0
    controller.paused = True
    assert controller.remaining_sec() == 6.0


def test_remaining_time_is_unavailable_without_a_fixed_phase_duration():
    controller = BreakinController(FakeSerial())
    assert controller.remaining_sec() is None
    controller.current_phase = BreakinPhase("condition", duration_sec=0, pwm=80)
    assert controller.remaining_sec() == 0.0
