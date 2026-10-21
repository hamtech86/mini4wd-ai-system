import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

from controllers.ui_benchmark_presets import BENCHMARK_PRESETS


def test_main_window_builds_offscreen_without_hardware_connection(monkeypatch, tmp_path):
    import ui.main_window as base_ui
    import app.main as main_app

    class FakeBatteryTab(QWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(kwargs.get("parent"))

        def set_connected(self, connected):
            self.connected = connected

    database_path = str(tmp_path / "ui-smoke.db")
    monkeypatch.setattr(base_ui, "resolve_database_path", lambda **kwargs: database_path)
    monkeypatch.setattr(main_app, "BatteryTab", FakeBatteryTab)
    app = QApplication.instance() or QApplication([])
    window = main_app.MainWindow({"breakin_controller": None, "serial_controller": None,
                                  "battery_serial_controller": None})
    try:
        assert window.motor_serial_status.text().startswith("MOTOR: DISCONNECTED")
        assert window.motor_connect.isEnabled()
        assert {window.recipe.itemText(index) for index in range(window.recipe.count())} == {
            "STD-T", "Full-T", "STD-I", "Full-I", "TUNE_BASIC_INPUT_3V_CHECK"
        }
        window.recipe.setCurrentIndex(window.recipe.findData("TUNE_BASIC_INPUT_3V_CHECK"))
        assert "limited" in window.sequence_status.text().lower()
        assert len(window.sequence_checks) == 1
        assert window.sequence_checks[0][0] == "TUNE_BASIC_INPUT_3V_CHECK"
        assert window.emergency_stop_fixed.isEnabled()
        assert window.sequence_all.isHidden()
        assert window.sequence_none.isHidden()
        assert window.sequence_execute.isHidden()
        assert window.sequence_stop.isHidden()
        assert not hasattr(window, "sequence_executor")
        assert not hasattr(window, "sequence_timer")
        assert not hasattr(window, "pause_button")
        assert not hasattr(window, "resume_button")
        assert window.ui_log.isReadOnly()
        assert {"DIR", "PWM", "INPUT VOLTAGE", "MOTOR VOLTAGE",
                "DRIVER INPUT CURRENT", "ELAPSED", "REMAIN"} <= set(window.progress)
        # Main execution telemetry has one canonical display; the supplemental
        # live panel must not duplicate DIR/PWM/voltage/current values.
        assert set(window.live) == {"Arduino", "RPM", "STATE", "TEMP"}
    finally:
        window.close()


def test_runtime_telemetry_refresh_keeps_sensor_values_visible(monkeypatch, tmp_path):
    from types import SimpleNamespace
    import ui.main_window as base_ui
    import app.main as main_app

    class FakeBatteryTab(QWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(kwargs.get("parent"))

        def set_connected(self, connected):
            self.connected = connected

    database_path = str(tmp_path / "ui-runtime-smoke.db")
    monkeypatch.setattr(base_ui, "resolve_database_path", lambda **kwargs: database_path)
    monkeypatch.setattr(main_app, "BatteryTab", FakeBatteryTab)
    app = QApplication.instance() or QApplication([])
    window = main_app.MainWindow({"breakin_controller": None, "serial_controller": None,
                                  "battery_serial_controller": None})
    measurement = SimpleNamespace(
        direction="FWD", pwm=39, voltage1=3.065, voltage2=0.306,
        motor_voltage=2.758, current1=0.059, state="RUN",
        motor_temperature=23.8,
    )
    controller = SimpleNamespace(
        serial=SimpleNamespace(connected=True, direction="FWD", last_pwm=39),
        measurement_manager=SimpleNamespace(last_measurement=measurement),
        running=True,
        current_phase=SimpleNamespace(name="BREAK_IN", direction="FWD"),
        current_phase_index=0,
        total_phases=1,
        current_pwm=39,
        elapsed_sec=lambda: 1.2,
        remaining_sec=lambda: 12.3,
    )
    window.breakin_controller = controller
    try:
        # Regression: refresh_runtime used to index self.live["V"] after the
        # canonical telemetry change removed that duplicate field, raising
        # KeyError and preventing every execution field from being refreshed.
        window.refresh_runtime()
        assert window.progress["INPUT VOLTAGE"].text() == "3.06 V"
        assert window.progress["MOTOR VOLTAGE"].text() == "2.76 V"
        assert window.progress["DRIVER INPUT CURRENT"].text() == "0.059 A"
        assert window.progress["DIR"].text() == "FWD"
        assert window.progress["PWM"].text() == "39"
        assert window.progress["ELAPSED"].text() == "1.2 s"
        assert window.progress["REMAIN"].text() == "12.3 s"
    finally:
        window.close()



def test_emergency_stop_latches_restart_and_keeps_stop_available(monkeypatch, tmp_path):
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
    window = main_app.MainWindow({"breakin_controller": None, "serial_controller": None,
                                  "battery_serial_controller": None})
    class FakeStopController:
        def __init__(self):
            self.calls = 0

        def emergency_stop(self):
            self.calls += 1
            return {"errors": ["serial write failed"],
                    "serial_result": {"pwm_zero": False, "stop_command": False,
                                      "errors": ["serial write failed"]}}

    try:
        fake_controller = FakeStopController()
        window.breakin_controller = fake_controller
        assert window.emergency_stop_fixed.isEnabled()
        window.emergency_stop_fixed.click()
        assert fake_controller.calls == 1
        assert window._stop_latched is True
        assert window.emergency_stop_fixed.isEnabled()
        assert window.error_code_label.text() == "Error Code: EMERGENCY_STOP_PATH_ERROR"
        assert "serial write failed" in window.error_message_label.text()
        assert not window.start.isEnabled()
        assert not window.recipe.isEnabled()
        # A stop request with no physical confirmation must not start another run.
        window._start_benchmark()
        assert window.error_code_label.text() == "Error Code: STOP_LATCHED"
        assert not window.start.isEnabled()
    finally:
        window.close()
