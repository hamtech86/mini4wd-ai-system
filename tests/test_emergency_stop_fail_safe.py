"""Regression tests for best-effort emergency-stop failure paths."""

from communication.serial_controller import SerialController
from controllers.breakin_controller import BreakinController


class FakeSerial:
    def __init__(self, fail_on=None, fail_close=False):
        self.fail_on = fail_on
        self.fail_close = fail_close
        self.writes = []
        self.closed = False

    def write(self, payload):
        command = payload.decode("utf-8").strip()
        self.writes.append(command)
        if command == self.fail_on:
            raise OSError(f"simulated write failure: {command}")

    def close(self):
        self.closed = True
        if self.fail_close:
            raise OSError("simulated close failure")


def test_emergency_stop_attempts_stop_after_pwm_zero_write_fails():
    serial = SerialController()
    handle = FakeSerial(fail_on="PWM=0")
    serial.serial = handle
    serial.connected = True

    result = serial.emergency_stop()

    assert handle.writes == ["PWM=0", "STOP"]
    assert handle.closed
    assert serial.serial is None
    assert serial.connected is False
    assert result is False


def test_emergency_stop_closes_and_clears_state_when_close_raises():
    serial = SerialController()
    handle = FakeSerial(fail_close=True)
    serial.serial = handle
    serial.connected = True

    result = serial.emergency_stop()

    assert handle.writes == ["PWM=0", "STOP"]
    assert handle.closed
    assert serial.serial is None
    assert serial.connected is False
    assert result is False


def test_controller_checkpoint_failure_does_not_block_serial_stop(monkeypatch):
    class StopTransport:
        called = False

        def emergency_stop(self):
            self.called = True
            return True

    transport = StopTransport()
    controller = BreakinController(serial_controller=transport)
    controller.running = True
    controller.paused = True

    def fail_checkpoint():
        raise OSError("simulated checkpoint failure")

    monkeypatch.setattr(controller, "_save_checkpoint", fail_checkpoint)
    result = controller.emergency_stop()

    assert controller.running is False
    assert controller.paused is False
    assert transport.called is True
    assert result is True



def test_emergency_stop_clears_saved_resume_checkpoint(monkeypatch, tmp_path):
    class StopTransport:
        def emergency_stop(self):
            return True

    controller = BreakinController(serial_controller=StopTransport())
    checkpoint = tmp_path / "breakin_resume.json"
    monkeypatch.setattr(BreakinController, "CHECKPOINT_PATH", checkpoint)

    def save_checkpoint():
        checkpoint.write_text('{"recipe": "TUNE_BASIC"}', encoding="utf-8")

    monkeypatch.setattr(controller, "_save_checkpoint", save_checkpoint)
    controller.emergency_stop()

    assert not checkpoint.exists()
