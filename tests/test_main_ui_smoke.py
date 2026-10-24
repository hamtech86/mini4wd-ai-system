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
            "STD-I", "Full-I", "TUNE_BASIC (SELECT / RESUME PLAN ONLY)",
        "TUNE_BASIC_INPUT_3V_CHECK"
        }
        assert window.recipe.findData("TUNE_BASIC") >= 0
        # Direct/programmatic invocation must be blocked as well as the UI option.
        window._start_tunebasic_recipe()
        assert window.error_code_label.text() == "Error Code: TUNEBASIC_BLOCKED_UNTIL_ISSUE98"
        from types import SimpleNamespace
        window.breakin_controller = SimpleNamespace(resume_checkpoint=lambda: {
            "recipe": "TUNE_BASIC", "phase_name": "FWD_3V_START", "phase_elapsed_sec": 4.5
        })
        window.recipe.setCurrentIndex(window.recipe.findData("TUNE_BASIC"))
        assert "RESUME PLAN ONLY" in window.sequence_status.text()
        assert "FWD_3V_START" in window.sequence_status.text()
        assert "4.5s elapsed" in window.sequence_status.text()
        assert "FWD_3V_START" in window.phase_detail.text()
        assert not window.start.isEnabled()
        assert not window.sequence_execute.isEnabled()
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

def test_late_worker_success_signal_cannot_overwrite_emergency_stop(monkeypatch, tmp_path):
    import ui.main_window as base_ui
    import app.main as main_app

    class FakeBatteryTab(QWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(kwargs.get("parent"))

        def set_connected(self, connected):
            self.connected = connected

    database_path = str(tmp_path / "ui-late-success-after-stop.db")
    monkeypatch.setattr(base_ui, "resolve_database_path", lambda **kwargs: database_path)
    monkeypatch.setattr(main_app, "BatteryTab", FakeBatteryTab)
    app = QApplication.instance() or QApplication([])

    for callback in ("complete", "_limited_tunebasic_completed"):
        window = main_app.MainWindow({
            "breakin_controller": None,
            "serial_controller": None,
            "battery_serial_controller": None,
        })
        try:
            window._stop_latched = True
            window.database_updated = False
            window.last_result_data = {"stale": True}
            window.update_db.setEnabled(True)
            window.copy.setEnabled(True)
            window.raw_log.setEnabled(True)
            window.run_state.setText("STOP REQUESTED / PHYSICAL STOP UNCONFIRMED")
            window.result["STATUS"].setText("STOP REQUESTED / UNCONFIRMED")

            if callback == "complete":
                window.complete({"result": "late"}, False)
            else:
                window._limited_tunebasic_completed({"result": "late"})

            assert window._stop_latched is True
            assert window.result["STATUS"].text() == "STOP REQUESTED / UNCONFIRMED"
            assert window.run_state.text() == "STOP REQUESTED / PHYSICAL STOP UNCONFIRMED"
            assert window.database_updated is False
            assert window.last_result_data is None
            assert not window.update_db.isEnabled()
            assert not window.copy.isEnabled()
            assert not window.raw_log.isEnabled()
        finally:
            window.close()




def test_recipe_combo_uses_stable_width_policy_across_tunebasic_selection(monkeypatch, tmp_path):
    import ui.main_window as base_ui
    import app.main as main_app
    from PyQt5.QtWidgets import QComboBox

    class FakeBatteryTab(QWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(kwargs.get("parent"))

        def set_connected(self, connected):
            self.connected = connected

    database_path = str(tmp_path / "ui-recipe-width.db")
    monkeypatch.setattr(base_ui, "resolve_database_path", lambda **kwargs: database_path)
    monkeypatch.setattr(main_app, "BatteryTab", FakeBatteryTab)
    app = QApplication.instance() or QApplication([])
    window = main_app.MainWindow({
        "breakin_controller": None,
        "serial_controller": None,
        "battery_serial_controller": None,
    })
    try:
        combo = window.recipe
        assert combo.sizeAdjustPolicy() == QComboBox.AdjustToMinimumContentsLengthWithIcon
        assert combo.minimumContentsLength() >= len("TUNE_BASIC_INPUT_3V_CHECK")
        combo.setCurrentIndex(combo.findData("TUNE_BASIC_INPUT_3V_CHECK"))
        app.processEvents()
        width_limited = combo.sizeHint().width()
        combo.setCurrentIndex(combo.findData("STD-I"))
        app.processEvents()
        width_short = combo.sizeHint().width()
        assert width_limited == width_short
    finally:
        window.close()

def test_tunebasic_phase_detail_wraps_without_forcing_horizontal_growth(monkeypatch, tmp_path):
    import ui.main_window as base_ui
    import app.main as main_app
    from PyQt5.QtWidgets import QSizePolicy

    class FakeBatteryTab(QWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(kwargs.get("parent"))

        def set_connected(self, connected):
            self.connected = connected

    database_path = str(tmp_path / "ui-phase-wrap.db")
    monkeypatch.setattr(base_ui, "resolve_database_path", lambda **kwargs: database_path)
    monkeypatch.setattr(main_app, "BatteryTab", FakeBatteryTab)
    app = QApplication.instance() or QApplication([])
    window = main_app.MainWindow({
        "breakin_controller": None,
        "serial_controller": None,
        "battery_serial_controller": None,
    })
    try:
        window.recipe.setCurrentIndex(window.recipe.findData("TUNE_BASIC_INPUT_3V_CHECK"))
        app.processEvents()
        assert window.phase_detail.wordWrap() is True
        assert window.phase_detail.sizePolicy().horizontalPolicy() == QSizePolicy.Ignored
        assert "limited" in window.sequence_status.text().lower()
    finally:
        window.close()




def test_verified_fresh_connection_enables_explicit_arm_without_driving(monkeypatch, tmp_path):
    import ui.main_window as base_ui
    import app.main as main_app

    class FakeBatteryTab(QWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(kwargs.get("parent"))

        def set_connected(self, connected):
            self.connected = connected

    class FakeMotorController:
        def __init__(self):
            self.connected = False
            self.identity_verified = False
            self.device_info = None
            self.arm_calls = 0

        def connect(self):
            self.connected = True
            self.identity_verified = True
            self.device_info = {
                "MODEL": "MOTOR_BREAKIN_V3", "FW": "3.03",
                "BUILD": "EXPLICIT-ARM-STOP-ACK-20261023-01", "ID": "000001",
            }
            return True

        def arm(self):
            self.arm_calls += 1
            return True

    database_path = str(tmp_path / "ui-explicit-arm.db")
    monkeypatch.setattr(base_ui, "resolve_database_path", lambda **kwargs: database_path)
    monkeypatch.setattr(main_app, "BatteryTab", FakeBatteryTab)
    app = QApplication.instance() or QApplication([])
    motor = FakeMotorController()
    window = main_app.MainWindow({
        "breakin_controller": None,
        "serial_controller": motor,
        "battery_serial_controller": None,
    })
    # MainWindow resolves the motor transport from its own serial_controller
    # attribute (or breakin_controller.serial_controller); context injection
    # alone is not wired by this app subclass.
    window.serial_controller = motor
    try:
        assert not window.motor_arm.isEnabled()
        window.connect_motor_serial()
        assert window._identity_verified(motor)
        assert window.motor_arm.isEnabled()
        assert motor.arm_calls == 0
        window.motor_arm.click()
        assert motor.arm_calls == 1
        assert window.motor_arm.isEnabled() is False
        assert window._arm_accepted is True
    finally:
        window.close()


def test_stop_latch_keeps_arm_disabled_after_reconnect(monkeypatch, tmp_path):
    import ui.main_window as base_ui
    import app.main as main_app

    class FakeBatteryTab(QWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(kwargs.get("parent"))

        def set_connected(self, connected):
            self.connected = connected

    class FakeMotorController:
        def __init__(self):
            self.connected = False
            self.identity_verified = False
            self.device_info = None

        def connect(self):
            self.connected = True
            self.identity_verified = True
            self.device_info = {
                "MODEL": "MOTOR_BREAKIN_V3", "FW": "3.03",
                "BUILD": "EXPLICIT-ARM-STOP-ACK-20261023-01", "ID": "000001",
            }
            return True

    database_path = str(tmp_path / "ui-arm-stop-latch.db")
    monkeypatch.setattr(base_ui, "resolve_database_path", lambda **kwargs: database_path)
    monkeypatch.setattr(main_app, "BatteryTab", FakeBatteryTab)
    app = QApplication.instance() or QApplication([])
    motor = FakeMotorController()
    window = main_app.MainWindow({
        "breakin_controller": None,
        "serial_controller": motor,
        "battery_serial_controller": None,
    })
    window.serial_controller = motor
    try:
        window._stop_latched = True
        window.connect_motor_serial()
        assert window._identity_verified(motor)
        assert not window.motor_arm.isEnabled()
        assert "RESTART REQUIRED AFTER STOP" in window.motor_serial_status.text()
    finally:
        window.close()


def test_benchmark_requires_explicit_arm_after_identity_verification(monkeypatch, tmp_path):
    import ui.main_window as base_ui
    import app.main as main_app

    class FakeBatteryTab(QWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(kwargs.get("parent"))

        def set_connected(self, connected):
            self.connected = connected

    class FakeMotorController:
        connected = True
        identity_verified = True
        device_info = {
            "MODEL": "MOTOR_BREAKIN_V3", "FW": "3.03",
            "BUILD": "EXPLICIT-ARM-STOP-ACK-20261023-01", "ID": "000001",
        }

    database_path = str(tmp_path / "ui-arm-required.db")
    monkeypatch.setattr(base_ui, "resolve_database_path", lambda **kwargs: database_path)
    monkeypatch.setattr(main_app, "BatteryTab", FakeBatteryTab)
    app = QApplication.instance() or QApplication([])
    motor = FakeMotorController()
    window = main_app.MainWindow({
        "breakin_controller": None,
        "serial_controller": motor,
        "battery_serial_controller": None,
    })
    # app.main.MainWindow resolves its active controller from its own attribute
    # (or the break-in controller), not solely from the constructor context.
    window.serial_controller = motor
    try:
        window._start_benchmark()
        assert window.error_code_label.text() == "Error Code: MOTOR_NOT_ARMED"
        assert "ARM REQUIRED" in window.run_state.text()
        assert window.breakin_worker is None
    finally:
        window.close()


def test_limited_tunebasic_requires_exact_authorized_firmware_build(monkeypatch, tmp_path):
    import app.main as main_app
    import ui.main_window as base_ui

    class FakeBatteryTab(QWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(kwargs.get("parent"))

        def set_connected(self, connected):
            self.connected = connected

    class FakeMotorController:
        connected = True
        identity_verified = True
        device_info = {
            "MODEL": "MOTOR_BREAKIN_V3", "FW": "3.03",
            # Validly formatted, but not the exact build authorized by Issue #98.
            "BUILD": "OTHER-20261024-01", "ID": "000001",
        }

    database_path = str(tmp_path / "limited-tunebasic-fw-gate.db")
    monkeypatch.setattr(base_ui, "resolve_database_path", lambda **kwargs: database_path)
    monkeypatch.setattr(main_app, "BatteryTab", FakeBatteryTab)
    app = QApplication.instance() or QApplication([])
    motor = FakeMotorController()
    window = main_app.MainWindow({
        "breakin_controller": None,
        "serial_controller": motor,
        "battery_serial_controller": None,
    })
    window.serial_controller = motor
    window._arm_accepted = True
    try:
        window._start_limited_tunebasic_check()
        assert window.error_code_label.text() == "Error Code: MOTOR_FIRMWARE_BUILD_MISMATCH"
        assert "No drive command was issued" in window.error_message_label.text()
        assert "FIRMWARE BUILD MISMATCH" in window.run_state.text()
        assert window.breakin_worker is None
    finally:
        window.close()
