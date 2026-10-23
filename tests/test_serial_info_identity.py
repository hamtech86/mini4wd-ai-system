"""Regression tests for strict motor INFO identity and RawLog exclusion."""
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
    assert controller.set_pwm(0) == "PWM=0"
    assert controller.send_command("STOP") == "STOP"
    assert handle.writes == ["PWM=0", "STOP"]


def test_valid_info_verifies_expected_model_and_allows_extension_keys():
    controller = SerialController()
    line = VALID_INFO + ",EXTRA=reserved-for-future"
    controller.serial = FakeSerial([(line + "\n").encode("utf-8")])
    controller.connected = True

    assert controller._verify_info_response(timeout=0.1) is True
    assert controller.identity_verified is True
    assert controller.device_info["MODEL"] == "MOTOR_BREAKIN_V3"
    assert "EXTRA" not in controller.device_info


def test_wrong_info_model_does_not_verify_identity():
    controller = SerialController()
    line = VALID_INFO.replace("MODEL=MOTOR_BREAKIN_V3", "MODEL=BATTERY_DISCHARGE")
    controller.serial = FakeSerial([(line + "\n").encode("utf-8")])
    controller.connected = True

    assert controller._verify_info_response(timeout=0.1) is False
    assert controller.identity_verified is False


def test_info_rows_are_excluded_from_raw_log():
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
    assert "INFO," not in controller.raw_log
    assert "CAL,ACS1=2.50,ACS2=2.51" in controller.raw_log
    assert data_line in controller.raw_log



def test_unexpected_info_during_armed_run_marks_reboot_and_revokes_token():
    controller = SerialController()
    controller.serial = FakeSerial([(VALID_INFO + "\n").encode("utf-8")])
    controller.connected = True
    controller.identity_verified = True
    controller.device_info = {"TYPE": "MOTOR", "MODEL": "MOTOR_BREAKIN_V3",
                              "FW": "3.03", "BUILD": "EXPLICIT-ARM-STOP-ACK-20261023-01",
                              "ID": "000001"}
    controller._active_arm_token = "DEADBEEF"

    assert controller.read_measurement() is None
    assert controller.device_reboot_detected is True
    assert "reboot suspected" in controller.device_reboot_reason.lower()
    assert controller.device_reboot_raw_line == VALID_INFO
    assert controller._active_arm_token is None
    assert controller.identity_verified is False
    assert controller.device_info is None
    assert "INFO," not in controller.raw_log


def test_info_during_idle_read_is_not_misclassified_as_reboot():
    controller = SerialController()
    controller.serial = FakeSerial([(VALID_INFO + "\n").encode("utf-8")])
    controller.connected = True

    assert controller.read_measurement() is None
    assert controller.device_reboot_detected is False
    assert controller.identity_verified is True
