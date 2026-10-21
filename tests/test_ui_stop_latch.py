"""Regression tests for the UI emergency-stop latch."""
import pytest

from PyQt5.QtWidgets import QApplication, QWidget


@pytest.fixture
def stop_latched_window(monkeypatch, tmp_path):
    import ui.main_window as base_ui
    import app.main as main_app

    class FakeBatteryTab(QWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(kwargs.get("parent"))

        def set_connected(self, connected):
            self.connected = connected

    database_path = str(tmp_path / "ui-stop-latch.db")
    monkeypatch.setattr(base_ui, "resolve_database_path", lambda **kwargs: database_path)
    monkeypatch.setattr(main_app, "BatteryTab", FakeBatteryTab)
    app = QApplication.instance() or QApplication([])
    window = main_app.MainWindow({
        "breakin_controller": None,
        "serial_controller": None,
        "battery_serial_controller": None,
    })
    yield window
    window.close()
    app.processEvents()


def test_emergency_stop_latches_ui_and_blocks_all_start_entry_points(stop_latched_window):
    window = stop_latched_window

    class FakeController:
        def __init__(self):
            self.stop_calls = 0
            self.start_calls = 0

        def emergency_stop(self):
            self.stop_calls += 1
            return False

    controller = FakeController()
    window.breakin_controller = controller

    window.stop_run()

    assert controller.stop_calls == 1
    assert window._stop_latched is True
    assert not window.start.isEnabled()
    assert not window.sequence_execute.isEnabled()
    assert not window.recipe.isEnabled()
    assert "RESTART BLOCKED" in window.result["STATUS"].text()

    # Both normal and benchmark entry points must refuse to launch after STOP.
    window._execute_selected_sequences()
    window._start_benchmark()
    assert controller.start_calls == 0
    assert not window.start.isEnabled()
    assert not window.sequence_execute.isEnabled()
