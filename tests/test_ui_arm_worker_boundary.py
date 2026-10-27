"""UI/worker-boundary tests for explicit ARM after normal completion.

These tests are hardware-independent. The fake worker captures whether the UI
permits worker creation; controller token revocation is tested separately against
SerialController's command path.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget


class FakeSignal:
    def connect(self, callback):
        self.callback = callback


class FakeMotorController:
    connected = True
    identity_verified = True
    device_info = {
        "MODEL": "MOTOR_BREAKIN_V3",
        "FW": "3.03",
        "BUILD": "UI-ARM-BOUNDARY-TEST",
        "ID": "000001",
    }

    def __init__(self):
        self.arm_calls = 0
        self._active_arm_token = None

    def arm(self):
        self.arm_calls += 1
        self._active_arm_token = f"token-{self.arm_calls}"
        return True

    def stop_breakin(self):
        self._active_arm_token = None
        return "STOP"


class FakeWorker:
    instances = []

    def __init__(self, controller, recipe, benchmark):
        self.controller = controller
        self.recipe = recipe
        self.benchmark = benchmark
        self.completed = FakeSignal()
        self.failed = FakeSignal()
        self.finished = FakeSignal()
        self.started = False
        self.__class__.instances.append(self)

    def start(self):
        self.started = True


def test_worker_boundary_requires_new_ui_arm_after_normal_completion(
    monkeypatch, tmp_path
):
    from types import SimpleNamespace
    import ui.main_window as base_ui
    import app.main as main_app

    class FakeBatteryTab(QWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(kwargs.get("parent"))

        def set_connected(self, connected):
            self.connected = connected

    database_path = str(tmp_path / "ui-arm-worker-boundary.db")
    monkeypatch.setattr(base_ui, "resolve_database_path", lambda **kwargs: database_path)
    monkeypatch.setattr(main_app, "BatteryTab", FakeBatteryTab)
    monkeypatch.setattr(main_app, "BreakinWorker", FakeWorker)
    FakeWorker.instances = []

    app = QApplication.instance() or QApplication([])
    motor = FakeMotorController()
    window = main_app.MainWindow({
        "breakin_controller": None,
        "serial_controller": motor,
        "battery_serial_controller": None,
    })
    try:
        # Model a successful prior UI ARM followed by normal STOP/token revoke.
        assert motor.arm() is True
        old_token = motor._active_arm_token
        assert old_token
        assert motor.stop_breakin() == "STOP"
        assert motor._active_arm_token is None
        window._arm_accepted = True
        window._run_completed_normally = True
        window.finished()

        assert window._arm_accepted is False
        assert window.motor_arm.isEnabled()

        # No new explicit UI ARM: the worker must not be constructed or started,
        # and the serial controller must receive no further ARM call.
        window._start_benchmark()
        assert window.error_code_label.text() == "Error Code: MOTOR_NOT_ARMED"
        assert window.breakin_worker is None
        assert FakeWorker.instances == []
        assert motor.arm_calls == 1
        assert motor._active_arm_token is None

        # Supply a non-hardware controller stub only after the blocked attempt.
        window.breakin_controller = SimpleNamespace()

        # A fresh operator click is the only path that re-authorizes a run.
        window.motor_arm.click()
        assert window._arm_accepted is True
        assert motor.arm_calls == 2
        new_token = motor._active_arm_token
        assert new_token and new_token != old_token

        # The accepted UI state now permits the worker boundary to be crossed.
        # The fake worker deliberately does not run motor-control code.
        window._start_benchmark()
        assert len(FakeWorker.instances) == 1
        assert FakeWorker.instances[0].started is True
        assert FakeWorker.instances[0].controller is window.breakin_controller
        assert motor.arm_calls == 2
        assert motor._active_arm_token == new_token
    finally:
        window.close()
