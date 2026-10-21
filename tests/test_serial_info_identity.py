"""Regression tests for motor device INFO identity gating."""
from communication.serial_controller import SerialController


class FakeSerial:
    def __init__(self, lines=()):
        self.lines = list(lines)
        self.writes = []
        self.timeout = 1
        self.closed = False

    @property
    def in_waiting(self):
        return bool(self.lines)

    def readline(self):
        return self.lines.pop(0) if self.lines else b""

    def write(self, payload):
        self.writes.append(payload.decode("utf-8").strip())

    def close(self):
        self.closed = True


VALID_INFO = "INFO,TYPE=MOTOR,MODEL=MOTOR_BREAKIN_V3,FW=3.00,BUILD=ACS-CAL-LOG-20261013-01,ID=MOTOR01"


def test_drive_commands_are_blocked_until_info_identity_is_verified():
    controller = SerialController()
    handle = FakeSerial()
    controller.serial = handle
    controller.connected = True

    assert controller.forward() is False
    assert controller.reverse() is False
    assert controller.set_pwm(60) is False
    assert handle.writes == []

    # Emergency commands remain available while identity is unknown.
    assert controller.set_pwm(0) == "PWM=0"
    assert controller.send_command("STOP") == "STOP"
    assert handle.writes == ["PWM=0", "STOP"]


def test_valid_info_response_verifies_only_the_expected_motor_model():
    controller = SerialController()
    controller.serial = FakeSerial([(VALID_INFO + "\n").encode("utf-8")])
    controller.connected = True

    assert controller._verify_info_response(timeout=0.1) is True
    assert controller.identity_verified is True
    assert controller.device_info["MODEL"] == "MOTOR_BREAKIN_V3"
    assert controller.device_info["FW"] == "3.00"


def test_wrong_info_model_does_not_verify_identity():
    controller = SerialController()
    line = VALID_INFO.replace("MODEL=MOTOR_BREAKIN_V3", "MODEL=BATTERY_DISCHARGE")
    controller.serial = FakeSerial([(line + "\n").encode("utf-8")])
    controller.connected = True

    assert controller._verify_info_response(timeout=0.1) is False
    assert controller.identity_verified is False
    assert "Unexpected motor device identity" in controller.identity_error



def test_info_allows_unknown_extension_key_without_changing_identity():
    controller = SerialController()
    line = VALID_INFO + ",EXTRA=reserved-for-future"
    controller.serial = FakeSerial([(line + "\n").encode("utf-8")])
    controller.connected = True

    assert controller._verify_info_response(timeout=0.1) is True
    assert controller.identity_verified is True
    assert "EXTRA" not in controller.device_info



def test_info_rows_are_excluded_from_raw_log_but_cal_and_data_are_kept():
    controller = SerialController()
    data_line = "DATA," + ",".join(["0"] * 25)
    handle = FakeSerial([
        (VALID_INFO + "\n").encode("utf-8"),
        b"CAL,ACS1=2.50,ACS2=2.51\n",
        (data_line + "\n").encode("utf-8"),
    ])
    controller.serial = handle
    controller.connected = True

    assert controller.read_measurement() == data_line
    raw_log = controller.raw_log
    assert "INFO," not in raw_log
    assert "CAL,ACS1=2.50,ACS2=2.51" in raw_log
    assert data_line in raw_log
