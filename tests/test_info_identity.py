from collections import deque
from types import SimpleNamespace

import pytest

from communication.csv_parser import CSVParser
import communication.serial_controller as serial_controller_module


VALID_INFO = "INFO,TYPE=MOTOR,MODEL=MOTOR_BREAKIN_V3,FW=3.00,BUILD=build-123,ID=MOTOR-000042"


@pytest.mark.parametrize(
    "line",
    [
        VALID_INFO,
        "INFO,ID=MOTOR-000042,BUILD=build-123,FW=3.00,MODEL=MOTOR_BREAKIN_V3,TYPE=MOTOR",
    ],
)
def test_info_parser_accepts_required_fields_in_any_order(line):
    info = CSVParser().parse(line)
    assert info["record_type"] == "INFO"
    assert info["TYPE"] == "MOTOR"
    assert info["MODEL"] == "MOTOR_BREAKIN_V3"
    assert info["ID"] == "MOTOR-000042"


@pytest.mark.parametrize(
    "line",
    [
        "INFO,TYPE=MOTOR,MODEL=MOTOR_BREAKIN_V3,FW=3.00,BUILD=x",
        "INFO,TYPE=MOTOR,MODEL=MOTOR_BREAKIN_V3,FW=3.00,BUILD=x,ID=y,ID=z",
        "INFO,TYPE=MOTOR,MODEL=MOTOR_BREAKIN_V3,FW=3.00,BUILD=x,ID=",
        "INFO,TYPE=MOTOR,MODEL=MOTOR_BREAKIN_V3,FW=3.00,BUILD=x,ID=y,OTHER=z",
        "INFO,TYPE=MOTOR,MODEL=MOTOR_BREAKIN_V3,FW=3.00,BUILD=x,ID=y,broken",
    ],
)
def test_info_parser_rejects_missing_duplicate_empty_or_unknown_fields(line):
    with pytest.raises(ValueError):
        CSVParser().parse(line)


def test_info_record_does_not_weaken_fixed_data_column_contract():
    with pytest.raises(ValueError, match="Invalid CSV length"):
        CSVParser().parse("DATA,too,few,fields")


class FakeSerial:
    def __init__(self, response=None):
        self.response = response
        self.lines = deque()
        self.is_open = True
        self.writes = []
        self.timeout = 1

    @property
    def in_waiting(self):
        return sum(len(line) for line in self.lines)

    def reset_input_buffer(self):
        self.lines.clear()

    def reset_output_buffer(self):
        pass

    def write(self, payload):
        self.writes.append(payload)
        if payload == b"INFO\n" and self.response is not None:
            self.lines.append((self.response + "\r\n").encode())
        return len(payload)

    def readline(self):
        return self.lines.popleft() if self.lines else b""

    def close(self):
        self.is_open = False


def test_serial_connect_requests_info_and_verifies_expected_device(monkeypatch):
    fake = FakeSerial(VALID_INFO)
    monkeypatch.setattr(
        serial_controller_module,
        "serial",
        SimpleNamespace(Serial=lambda *args, **kwargs: fake),
    )
    monkeypatch.setattr(serial_controller_module.time, "sleep", lambda _: None)
    controller = serial_controller_module.SerialController()
    assert controller.connect() is True
    assert b"INFO\n" in fake.writes
    assert controller.identity_verified is True
    assert controller.device_info["BUILD"] == "build-123"
    assert controller.forward() == "FWD"
    assert b"FWD\n" in fake.writes
    controller.disconnect()
    assert controller.identity_verified is False


def test_serial_connect_rejects_wrong_model_and_blocks_drive(monkeypatch):
    fake = FakeSerial("INFO,TYPE=MOTOR,MODEL=OTHER,FW=3.00,BUILD=x,ID=y")
    monkeypatch.setattr(
        serial_controller_module,
        "serial",
        SimpleNamespace(Serial=lambda *args, **kwargs: fake),
    )
    monkeypatch.setattr(serial_controller_module.time, "sleep", lambda _: None)
    controller = serial_controller_module.SerialController()
    assert controller.connect() is True
    assert controller.identity_verified is False
    assert controller.forward() is False
    assert b"FWD\n" not in fake.writes
    assert controller.stop_breakin() == "STOP"
    assert b"STOP\n" in fake.writes
    controller.disconnect()


def test_drive_commands_fail_closed_without_verified_identity():
    controller = serial_controller_module.SerialController()
    fake = FakeSerial()
    controller.serial = fake
    controller.connected = True
    assert controller.reverse() is False
    assert controller.set_pwm(120) is False
    assert b"REV\n" not in fake.writes
    assert b"PWM=120\n" not in fake.writes
    assert controller.set_pwm(0) == "PWM=0"
    assert b"PWM=0\n" in fake.writes
