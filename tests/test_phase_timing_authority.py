import unittest
from unittest.mock import patch

from controllers.breakin_controller import BreakinController
from controllers.recipe import BreakinPhase


class FakeSerial:
    def set_pwm(self, _value):
        pass


class PhaseTimingAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.controller = BreakinController(FakeSerial())
        self.controller.current_phase = BreakinPhase("TEST", duration_sec=10)
        self.controller.phase_elapsed_before_pause = 0.0

    def test_remaining_uses_controller_effective_elapsed(self):
        with patch("controllers.breakin_controller.time.time", return_value=100.0):
            self.controller.phase_started_at = 90.0
            self.assertAlmostEqual(self.controller.effective_elapsed_sec(), 10.0)
            self.assertEqual(self.controller.remaining_sec(), 0.0)

    def test_pause_resume_preserves_effective_elapsed(self):
        with patch("controllers.breakin_controller.time.time", side_effect=[104.0, 104.0, 108.0, 111.0, 111.0]):
            self.controller.phase_started_at = 100.0
            self.controller.phase_elapsed_before_pause = 0.0
            self.assertAlmostEqual(self.controller.effective_elapsed_sec(), 4.0)

            # Same calculation used by pause(): freeze the authoritative time.
            self.controller.phase_elapsed_before_pause = self.controller.effective_elapsed_sec()
            self.controller.phase_started_at = 104.0
            self.assertAlmostEqual(self.controller.effective_elapsed_sec(), 4.0)
            self.assertAlmostEqual(self.controller.remaining_sec(), 6.0)

            self.assertAlmostEqual(self.controller.effective_elapsed_sec(), 7.0)
            self.assertAlmostEqual(self.controller.remaining_sec(), 3.0)


if __name__ == "__main__":
    unittest.main()
