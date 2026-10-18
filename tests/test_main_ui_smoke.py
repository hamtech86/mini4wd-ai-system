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
        assert set(BENCHMARK_PRESETS) <= {
            window.recipe.itemText(index) for index in range(window.recipe.count())
        }
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
