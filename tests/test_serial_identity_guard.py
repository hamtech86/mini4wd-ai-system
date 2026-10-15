import pytest

from communication.protocol import CSV_FIELDS
from communication.serial_controller import SerialController


INFO = "INFO,TYPE=MOTOR,MODEL=MOTOR_BREAKIN_V3,FW=3.00,BUILD=TEST-BUILD,ID=000001\n"


class FakePort:
    def __init__(self, lines=(), fail_writes=()):
        self.lines = [line.encode("utf-8") if isinstance(line, str) else line for line in lines]
        self.writes = []
        self.fail_writes = set(fail_writes)
        self.timeout = 1.0
        self.closed = False

    def write(self, data):
        self.writes.append(data)
        if len(self.writes) in self.fail_writes:
            raise OSError("simulated serial write failure")
        return len(data)

    @property
    def in_waiting(self):
        return len(self.lines)

    def readline(self):
        return self.lines.pop(0) if self.lines else b""

    def reset_input_buffer(self):
        self.lines.clear()

    def reset_output_buffer(self):
        self.writes.clear()

    def close(self):
        self.closed = True


def make_data_line():
    values = {
        "record_type": "DATA",
        "device_model": "MOTOR_BREAKIN_V3",
        "instance_id": "000011",
        "elapsed_time": 1000,
        "raw_acs1": 100,
        "raw_acs2": 101,
        "current1": 0.10,
        "current2": 0.09,
        "voltage1": 2.50,
        "voltage2": 0.20,
        "motor_voltage": 2.30,
        "pwm": 60,
        "direction": "FWD",
        "state": "RUN",
        "current_avg": 0.095,
        "power": 0.23,
        "current_ripple": 0.01,
        "voltage_ripple": 0.02,
        "peak_power": 0.30,
        "peak_current": 0.20,
        "peak_voltage": 2.50,
        "peak_pwm": 60,
        "brush_peak_current": 0.20,
        "raw_magnetic": 100,
        "magnetic_level": 2.0,
        "motor_temperature": 30.0,
    }
    return ",".join(str(values[field]) for field in CSV_FIELDS) + "\n"


def identified_controller(port=None):
    controller = SerialController()
    controller.connected = True
    controller.serial = port or FakePort()
    controller.device_info = {
        "TYPE": "MOTOR",
        "MODEL": "MOTOR_BREAKIN_V3",
        "FW": "3.00",
        "BUILD": "TEST-BUILD",
        "ID": "000001",
    }
    controller._identity_confirmed = True
    controller.identity_error = None
    return controller


@pytest.mark.parametrize(
    "command",
    ["START", "RESUME", "FWD", "REV", "PWM=1", "PWM=80", "VCTRL=ON", "TARGET=3.0"],
)
def test_drive_capable_commands_are_blocked_when_identity_is_unconfirmed(command):
    port = FakePort()
    controller = SerialController()
    controller.connected = True
    controller.serial = port

    with pytest.raises(RuntimeError, match="identity is unconfirmed"):
        controller.send_command(command)

    assert port.writes == []
    assert controller.command_log == []


def test_direction_and_pwm_helpers_do_not_mutate_state_when_rejected():
    port = FakePort()
    controller = SerialController()
    controller.connected = True
    controller.serial = port
    controller.direction = "FWD"
    controller.last_pwm = 12

    with pytest.raises(RuntimeError):
        controller.forward()
    with pytest.raises(RuntimeError):
        controller.reverse()
    with pytest.raises(RuntimeError):
        controller.set_pwm(80)

    assert controller.direction == "FWD"
    assert controller.last_pwm == 12
    assert port.writes == []


def test_safe_commands_are_available_without_identity():
    port = FakePort()
    controller = SerialController()
    controller.connected = True
    controller.serial = port

    for command in ("INFO", "STATUS", "PING", "PAUSE", "PWM=0", "STOP", "VCTRL=OFF"):
        assert controller.send_command(command) == command

    assert [item.decode("utf-8").strip() for item in port.writes] == [
        "INFO", "STATUS", "PING", "PAUSE", "PWM=0", "STOP", "VCTRL=OFF"
    ]


@pytest.mark.parametrize("line", [
    "INFO,TYPE=MOTOR,MODEL=MOTOR_BREAKIN_V3,FW=3.00,BUILD=TEST,ID=000001,ID=000002",
    "INFO,TYPE=MOTOR,MODEL=MOTOR_BREAKIN_V3,FW=3.00,BUILD=,ID=000001",
    "INFO,TYPE=BATTERY,MODEL=MOTOR_BREAKIN_V3,FW=3.00,BUILD=TEST,ID=000001",
    "INFO,TYPE=MOTOR,MODEL=UNKNOWN_MODEL,FW=3.00,BUILD=TEST,ID=000001",
    "INFO,TYPE=MOTOR,MODEL=MOTOR_BREAKIN_V3,FW=3.00,ID=000001",
])
def test_info_parser_rejects_incomplete_conflicting_or_unapproved_identity(line):
    with pytest.raises(ValueError):
        SerialController._parse_info_line(line)


def test_info_handshake_preserves_data_and_excludes_info_from_rawlog():
    data = make_data_line()
    port = FakePort([data, INFO])
    controller = SerialController()
    controller.connected = True
    controller.serial = port

    assert controller._acquire_device_info() is True
    assert controller.identified is True
    assert controller.device_info["MODEL"] == "MOTOR_BREAKIN_V3"

    measurement = controller.read_measurement()

    assert measurement is not None
    assert len(controller.last_raw_data.split(",")) == len(CSV_FIELDS) == 26
    assert controller.raw_log == data
    assert "INFO," not in controller.raw_log


def test_info_timeout_leaves_device_unidentified(monkeypatch):
    controller = SerialController()
    controller.INFO_TIMEOUT_SEC = 0.02
    controller.connected = True
    controller.serial = FakePort([])

    assert controller._acquire_device_info() is False
    assert controller.identified is False
    assert controller.device_info is None
    assert controller.identity_error == "info_timeout"


def test_unknown_and_malformed_commands_are_rejected_even_after_identification():
    port = FakePort()
    controller = identified_controller(port)

    for command in ("NOT_A_COMMAND", "PWM=999", "PWM=00", "PWM=0\nSTART", "TARGET=nan"):
        with pytest.raises(ValueError):
            controller.send_command(command)

    assert port.writes == []


def test_emergency_stop_attempts_stop_and_disconnect_after_pwm_write_failure():
    port = FakePort(fail_writes={1})
    controller = SerialController()
    controller.connected = True
    controller.serial = port

    with pytest.raises(OSError, match="simulated serial write failure"):
        controller.emergency_stop()

    assert [item.decode("utf-8").strip() for item in port.writes] == ["PWM=0", "STOP"]
    assert port.closed is True
    assert controller.connected is False
    assert controller.identified is False


def test_breakin_start_and_direct_phase_reject_before_state_changes():
    from types import SimpleNamespace
    from controllers.breakin_controller import BreakinController
    from controllers.recipe import BreakinPhase

    port = FakePort()
    serial = SerialController()
    serial.connected = True
    serial.serial = port
    controller = BreakinController(serial)

    with pytest.raises(RuntimeError, match="not identified"):
        controller.start(SimpleNamespace(name="TEST", phases=[]))

    assert controller.running is False
    assert controller.active_recipe_name is None
    assert port.writes == []

    with pytest.raises(RuntimeError, match="not identified"):
        controller.execute_phase(BreakinPhase("PHASE", 1, 80, "FWD"))

    assert controller.current_phase is None
    assert port.writes == []


def test_benchmark_and_sequence_entry_points_reject_unidentified_device():
    from types import SimpleNamespace
    from controllers.breakin_controller import BreakinController
    from controllers.breakin_sequence_adapter import BreakinSequenceAdapter
    from controllers.sequence_executor import SequenceExecutor
    from controllers.motor_benchmark import run_benchmark

    port = FakePort()
    serial = SerialController()
    serial.connected = True
    serial.serial = port
    controller = BreakinController(serial)

    with pytest.raises(RuntimeError, match="not identified"):
        run_benchmark(controller)
    assert controller.running is False
    assert controller.session is None

    adapter = BreakinSequenceAdapter(controller)
    sequence = SimpleNamespace(
        parameters={}, direction="FWD", pwm=80, sequence_id="SEQ-1",
        duration_sec=1, metadata={},
    )
    with pytest.raises(RuntimeError, match="not identified"):
        adapter.start_sequence(sequence)
    assert adapter._active is None
    assert port.writes == []

    executor = SequenceExecutor(adapter=adapter)
    with pytest.raises(RuntimeError, match="not identified"):
        executor.start()
    assert executor.running is False
    assert port.writes == []


def test_disconnect_clears_previously_validated_device_info():
    controller = identified_controller(FakePort())

    controller.disconnect()

    assert controller.connected is False
    assert controller.device_info is None
    assert controller.identified is False
    assert controller.identity_error == "disconnected"


def test_stop_breakin_still_sends_stop_after_pwm_zero_write_failure():
    port = FakePort(fail_writes={1})
    controller = SerialController()
    controller.connected = True
    controller.serial = port

    with pytest.raises(OSError, match="simulated serial write failure"):
        controller.stop_breakin()

    assert [item.decode("utf-8").strip() for item in port.writes] == ["PWM=0", "STOP"]
    assert controller.connected is True


def test_connect_explicitly_requests_and_validates_info(monkeypatch):
    from types import SimpleNamespace
    import communication.serial_controller as serial_module

    class InfoRespondingPort(FakePort):
        def write(self, data):
            result = super().write(data)
            if data == b"INFO\n":
                self.lines.append(INFO.encode("utf-8"))
            return result

    port = InfoRespondingPort()
    monkeypatch.setattr(serial_module, "serial", SimpleNamespace(Serial=lambda *args, **kwargs: port))
    monkeypatch.setattr(serial_module.time, "sleep", lambda _seconds: None)

    controller = SerialController()

    assert controller.connect() is True
    assert controller.identified is True
    assert controller.device_info["BUILD"] == "TEST-BUILD"
    assert [item.decode("utf-8").strip() for item in port.writes] == ["INFO"]


def test_registration_uses_connection_device_info_without_inserting_info_into_rawlog(tmp_path):
    from controllers.local_raw_log_breakin_controller import LocalRawLogBreakinController
    from raw_log_library import RawLogLibrary

    serial = identified_controller(FakePort())
    library = RawLogLibrary(tmp_path)
    controller = LocalRawLogBreakinController(
        serial_controller=serial,
        raw_log_library=library,
    )
    controller.active_instance_id = "INSTANCE-004"
    controller.active_recipe_name = "STD-T"
    raw_body = "DATA,1,2,3\\n"

    record = controller._register_raw_log(raw_body)

    assert record.device_type == "MOTOR"
    assert record.device_model == "MOTOR_BREAKIN_V3"
    assert record.firmware_version == "3.00"
    assert "device_build=TEST-BUILD" in record.notes
    assert "firmware_device_id=000001" in record.notes
    assert record.device_instance_id == "INSTANCE-004"
    assert library.read_raw(record.log_id) == raw_body
