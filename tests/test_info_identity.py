from collections import deque
from types import SimpleNamespace

import pytest

from communication.csv_parser import CSVParser
import communication.serial_controller as serial_controller_module
from communication.serial_manager import SerialReader


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
        "INFO,TYPE=MOTOR,MODEL=MOTOR_BREAKIN_V3,FW=3.00,BUILD=x,ID=y,broken",
    ],
)
def test_info_parser_rejects_missing_duplicate_empty_or_unknown_fields(line):
    with pytest.raises(ValueError):
        CSVParser().parse(line)


def test_data_still_requires_and_accepts_exactly_26_fields():
    with pytest.raises(ValueError, match="Invalid CSV length"):
        CSVParser().parse("DATA,too,few,fields")
    valid_data = ",".join(["DATA"] + ["0"] * 25)
    parsed = CSVParser().parse(valid_data)
    assert parsed["record_type"] == "DATA"
    assert len(parsed) == 26


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
        elif payload.startswith(b"ARM="):
            token = payload.decode().strip().split("=", 1)[1]
            self.lines.append(("ARMED," + token + "\r\n").encode())
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
    assert controller.arm() is True
    token = fake.writes[-1].decode().strip().split("=", 1)[1]
    assert controller.forward() == "FWD"
    assert f"FWD@{token}\n".encode() in fake.writes
    controller.disconnect()
    assert controller.identity_verified is False


@pytest.mark.parametrize(
    "response",
    [
        "INFO,TYPE=MOTOR,MODEL=OTHER,FW=3.00,BUILD=x,ID=y",
        "INFO,TYPE=MOTOR,MODEL=MOTOR_BREAKIN_V3,FW=unknown,BUILD=x,ID=y",
        "INFO,TYPE=MOTOR,MODEL=MOTOR_BREAKIN_V3,FW=3.00,BUILD=bad build,ID=y",
        "INFO,TYPE=MOTOR,MODEL=MOTOR_BREAKIN_V3,FW=3.00,BUILD=x,ID=bad!",
    ],
)
def test_serial_connect_rejects_invalid_identity_and_blocks_drive(monkeypatch, response):
    fake = FakeSerial(response)
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
    assert controller.send_command("RESUME") is False
    assert controller.set_pwm(120) is False
    assert b"REV\n" not in fake.writes
    assert b"RESUME\n" not in fake.writes
    assert b"PWM=120\n" not in fake.writes
    assert controller.set_pwm(0) == "PWM=0"
    assert b"PWM=0\n" in fake.writes


def test_serial_connect_times_out_without_info_and_keeps_drive_blocked(monkeypatch):
    fake = FakeSerial(response=None)
    monkeypatch.setattr(
        serial_controller_module,
        "serial",
        SimpleNamespace(Serial=lambda *args, **kwargs: fake),
    )
    monkeypatch.setattr(serial_controller_module.time, "sleep", lambda _: None)
    ticks = iter([0.0, 0.5, 1.1])
    monkeypatch.setattr(serial_controller_module.time, "monotonic", lambda: next(ticks))
    controller = serial_controller_module.SerialController()
    assert controller.connect() is True
    assert controller.identity_verified is False
    assert "timed out" in controller.identity_error.lower()
    assert controller.forward() is False
    assert b"FWD\\n" not in fake.writes
    controller.disconnect()


def test_info_identity_line_is_not_added_to_measurement_raw_log():
    controller = serial_controller_module.SerialController()
    fake = FakeSerial()
    fake.lines.append((VALID_INFO + "\\r\\n").encode())
    controller.serial = fake
    controller.connected = True
    controller.identity_verified = True
    assert controller.read_measurement() is None
    assert controller.raw_log == ""


def test_raw_log_keeps_cal_auxiliary_line_but_excludes_info():
    controller = serial_controller_module.SerialController()
    fake = FakeSerial()
    fake.lines.append((VALID_INFO + "\\r\\n").encode())
    fake.lines.append(b"CAL,1,512,513\\r\\n")
    controller.serial = fake
    controller.connected = True
    controller.identity_verified = True
    assert controller.read_measurement() is None
    assert controller.raw_log == "CAL,1,512,513\\r\\n"


def test_serial_reader_excludes_info_but_preserves_data_and_cal_raw_lines():
    class FakeCollector:
        def __init__(self):
            self.lines = []

        def append(self, line):
            self.lines.append(line)

    class FakePort:
        def __init__(self, lines):
            self.lines = deque(line.encode() for line in lines)
            self.is_open = True
            self.reader = None

        @property
        def in_waiting(self):
            return sum(len(line) for line in self.lines)

        def readline(self):
            line = self.lines.popleft()
            if not self.lines:
                self.reader.running = False
            return line

    data_line = ",".join(["DATA"] + ["0"] * 25) + "\\r\\n"
    cal_line = "CAL,1,512,513\\r\\n"
    collector = FakeCollector()
    port = FakePort([VALID_INFO + "\\r\\n", data_line, cal_line])
    reader = SerialReader(port, collector)
    port.reader = reader
    reader.run()
    assert collector.lines == [data_line, cal_line]



def test_info_parser_allows_unknown_extension_fields():
    info = CSVParser().parse("INFO,TYPE=MOTOR,MODEL=MOTOR_BREAKIN_V3,FW=3.00,BUILD=x,ID=y,OTHER=z")
    assert info["record_type"] == "INFO"
    assert info["MODEL"] == "MOTOR_BREAKIN_V3"
    assert info["OTHER"] == "z"
