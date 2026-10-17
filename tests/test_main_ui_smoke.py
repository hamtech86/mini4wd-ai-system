import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from controllers.ui_benchmark_presets import BENCHMARK_PRESETS


def test_main_window_builds_offscreen_without_hardware_connection(monkeypatch, tmp_path):
    import ui.main_window as base_ui
    import app.main as main_app

    database_path = str(tmp_path / "ui-smoke.db")
    monkeypatch.setattr(base_ui, "resolve_database_path", lambda **kwargs: database_path)
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
    finally:
        window.close()
