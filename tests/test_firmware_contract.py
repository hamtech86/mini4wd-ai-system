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

