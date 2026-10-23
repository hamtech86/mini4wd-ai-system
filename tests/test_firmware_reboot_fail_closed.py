"""Fail-closed regression tests for firmware reboot during an active run."""

import pytest

from controllers.breakin_controller import BreakinController


class EmptyMeasurementManager:
    def collect(self):
        return None


def test_controller_aborts_immediately_when_serial_reports_firmware_reboot():
    controller = BreakinController.__new__(BreakinController)
    controller.measurement_manager = EmptyMeasurementManager()

    class Serial:
        unexpected_reboot_detected = True

    controller.serial = Serial()
    controller.abort_reason = None
    controller.emergency_stop_called = False

    def emergency_stop():
        controller.emergency_stop_called = True

    controller.emergency_stop = emergency_stop

    with pytest.raises(RuntimeError, match="firmware reboot detected"):
        controller._collect_measurement(None)

    assert controller.emergency_stop_called is True
    assert "old ARM session invalidated" in controller.abort_reason
