"""Hardware-independent regression tests for explicit ARM token lifecycle."""

from communication.serial_controller import SerialController


class FakeSerial:
    def __init__(self):
        self.timeout = 0.01
        self.closed = False
        self._lines = []
        self.writes = []

    @property
    def in_waiting(self):
        return bool(self._lines)

    def write(self, payload):
        command = payload.decode("utf-8").strip()
        self.writes.append(command)
        if command.startswith("ARM="):
            token = command.split("=", 1)[1]
            self._lines.append(f"ARMED,{token}\n".encode("utf-8"))

    def readline(self):
        return self._lines.pop(0) if self._lines else b""

    def close(self):
        self.closed = True


def make_armed_controller():
    controller = SerialController()
    controller.serial = FakeSerial()
    controller.connected = True
    controller.identity_verified = True
    controller.device_info = {
        "MODEL": "MOTOR_BREAKIN_V3",
        "FW": "3.03",
        "BUILD": "TEST-BUILD",
        "ID": "TEST-DEVICE",
    }
    return controller


def test_normal_stop_revokes_token_and_blocks_drive_until_fresh_arm():
    controller = make_armed_controller()

    assert controller.arm() is True
    first_token = controller._active_arm_token
    assert first_token
    assert controller.forward() == "FWD"
    assert controller._active_arm_token == first_token

    assert controller.stop_breakin() == "STOP"
    assert controller._active_arm_token is None

    # STOP must leave the transport unable to issue a drive command using the
    # previous authorization. A fresh ARM handshake is required.
    assert controller.forward() is False
    assert controller._active_arm_token is None

    assert controller.arm() is True
    second_token = controller._active_arm_token
    assert second_token
    assert second_token != first_token
    assert controller.forward() == "FWD"
    assert controller.serial.writes[-1] == f"FWD@{second_token}"


def test_stop_command_revokes_token_even_without_successful_followup_drive():
    controller = make_armed_controller()
    assert controller.arm() is True
    assert controller._active_arm_token is not None

    assert controller.send_command("STOP") == "STOP"
    assert controller._active_arm_token is None
    assert controller.reverse() is False
    assert not any(command.startswith("REV@") for command in controller.serial.writes)
