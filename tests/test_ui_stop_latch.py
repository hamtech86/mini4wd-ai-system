"""Regression tests for UI emergency-stop latching and sensor display."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from types import SimpleNamespace
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



def test_runtime_displays_directional_input_voltage_and_physical_sensor_fields(stop_latched_window):
    window = stop_latched_window
    measurement = SimpleNamespace(
        direction="FWD", pwm=39, voltage1=3.065, voltage2=0.306,
        motor_voltage=2.758, current1=0.059, current_avg=0.071,
        state="RUN", motor_temperature=23.8,
    )
    controller = SimpleNamespace(
        serial=SimpleNamespace(connected=True, direction="FWD", last_pwm=39),
        measurement_manager=SimpleNamespace(last_measurement=measurement),
        running=True,
        current_phase=SimpleNamespace(name="BREAK_IN", direction="FWD", duration_sec=13.5),
        current_phase_index=0,
        total_phases=1,
        current_pwm=39,
        phase_elapsed_sec=lambda: 1.2,
    )
    window.breakin_controller = controller

    window.refresh_runtime()
    assert window.progress["INPUT VOLTAGE"].text() == "3.06 V"
    assert window.progress["MOTOR VOLTAGE"].text() == "2.76 V"
    assert window.progress["DRIVER INPUT CURRENT"].text() == "0.059 A"
    assert window.progress["DIR"].text() == "FWD"
    assert window.progress["PWM"].text() == "39"

    # Reverse uses voltage2; missing or non-finite values are not fabricated.
    measurement.direction = "REV"
    window.refresh_runtime()
    assert window.progress["INPUT VOLTAGE"].text() == "0.31 V"
    measurement.voltage2 = float("nan")
    window.refresh_runtime()
    assert window.progress["INPUT VOLTAGE"].text() == "--"
