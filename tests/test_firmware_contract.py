from pathlib import Path

from communication.protocol import CSV_FIELDS


ROOT = Path(__file__).resolve().parents[1]
FIRMWARE = (ROOT / "firmware" / "motor" / "MotoreRev.ino").read_text(encoding="utf-8")


def test_data_contract_remains_26_fields():
    assert len(CSV_FIELDS) == 26
    assert CSV_FIELDS[10] == "motor_voltage"
    assert CSV_FIELDS[25] == "motor_temperature"


def test_firmware_does_not_run_independent_voltage_feedback_loop():
    # The function may remain as unused legacy code, but the runtime loop must
    # never call it and legacy activation commands must not enable it.
    assert "voltageControlUpdate();" not in FIRMWARE
    assert 'sendError("VOLTAGE_CONTROL_OWNED_BY_HOST");' in FIRMWARE
    assert 'strcmp(cmd, "VCTRL=ON") == 0' in FIRMWARE
    assert 'strncmp(cmd, "TARGET=", 7) == 0' in FIRMWARE


def test_stop_and_pause_disable_hidden_voltage_control_and_zero_pwm():
    stop = FIRMWARE.rsplit("void stopMotor()", 1)[1].split("}", 1)[0]
    assert "voltageControl.enabled = false;" in stop
    assert "runtime.pwm = 0;" in stop
    pause = FIRMWARE.split('if (strcmp(cmd, "PAUSE") == 0)', 1)[1].split("return;", 1)[0]
    assert "voltageControl.enabled = false;" in pause
    assert "analogWrite(PIN_PWM, 0);" in pause


def test_calibration_snapshot_is_emitted_before_drive_direction_starts():
    fwd = FIRMWARE.split('if (strcmp(cmd, "FWD") == 0)', 1)[1].split("return;", 1)[0]
    rev = FIRMWARE.split('if (strcmp(cmd, "REV") == 0)', 1)[1].split("return;", 1)[0]
    assert fwd.index("sendCalibration();") < fwd.index("startForward();")
    assert rev.index("sendCalibration();") < rev.index("startReverse();")



def test_calibration_is_a_raw_auxiliary_line_not_a_data_column():
    serial_source = (ROOT / "communication" / "serial_controller.py").read_text(encoding="utf-8")
    collector_source = (ROOT / "communication" / "raw_log_collector.py").read_text(encoding="utf-8")
    assert 'if line.startswith("INFO,")' in serial_source
    assert "self.raw_log_collector.append(decoded)" in serial_source
    assert "self._lines.append(raw_line)" in collector_source
    # CAL is not filtered out; the exact received line is retained alongside
    # DATA lines, while the protocol schema remains exactly 26 DATA fields.
    assert "CAL," not in serial_source.split('if line.startswith("INFO,")', 1)[1].split("self.raw_log_collector.append(decoded)", 1)[0]


def test_measurement_and_feedback_validation_are_separate_layers():
    manager_source = (ROOT / "measurement" / "measurement_manager.py").read_text(encoding="utf-8")
    controller_source = (ROOT / "controllers" / "breakin_controller.py").read_text(encoding="utf-8")
    assert "math.isfinite(numeric[name])" in manager_source
    assert "def _measurement_is_valid_for_phase" in controller_source
    assert "self._measurement_is_valid_for_phase(phase, measurement)" in controller_source
    assert "self._consecutive_invalid_measurements += 1" in controller_source
    assert "self._consecutive_invalid_measurements = 0" in controller_source



def test_raw_capture_is_reset_before_start_can_emit_calibration():
    adapter_source = (
        ROOT / "controllers" / "local_raw_log_breakin_controller.py"
    ).read_text(encoding="utf-8")
    start_body = adapter_source.split("    def start(self, recipe", 1)[1].split(
        "    def _freeze_measurement_raw_log", 1
    )[0]
    assert start_body.index("self.serial.reset_raw_log()") < start_body.index(
        "super().start(recipe"
    )
    # The parent start executes phases, whose FWD/REV commands trigger CAL.
    # Firmware contract tests above assert CAL precedes startForward/startReverse.
    assert "super().start(recipe, instance_id=instance_id, resume=resume)" in start_body
