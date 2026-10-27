"""Hardware-independent fail-closed tests for the FW 3.03 ARM contract."""
import threading

import pytest

from communication import serial_controller as serial_module
from communication.serial_controller import SerialController


class FakeSerial:
    def __init__(self, arm_responses=None, disconnect_on_arm=False):
        self.timeout = 0.01
        self.closed = False
        self.lines = []
        self.writes = []
        self.arm_responses = arm_responses
        self.disconnect_on_arm = disconnect_on_arm
        self.controller = None

    @property
    def in_waiting(self):
        return bool(self.lines)

    def write(self, payload):
        command = payload.decode("utf-8").strip()
        self.writes.append(command)
        if command.startswith("ARM="):
            if self.disconnect_on_arm and self.controller is not None:
                self.controller.connected = False
                return
            if callable(self.arm_responses):
                self.arm_responses(self, command.split("=", 1)[1])
            elif self.arm_responses is not None:
                for response in self.arm_responses:
                    self.lines.append((response + "\n").encode("utf-8"))

    def readline(self):
        return self.lines.pop(0) if self.lines else b""

    def close(self):
        self.closed = True


def make_controller(monkeypatch, arm_responses=None, disconnect_on_arm=False):
    monkeypatch.setattr(serial_module.secrets, "token_hex", lambda n: "A1B2C3D4")
    controller = SerialController()
    fake = FakeSerial(arm_responses=arm_responses, disconnect_on_arm=disconnect_on_arm)
    fake.controller = controller
    controller.serial = fake
    controller.connected = True
    controller.identity_verified = True
    controller.device_info = {
        "TYPE": "MOTOR", "MODEL": "MOTOR_BREAKIN_V3", "FW": "3.03",
        "BUILD": "ARM-STOP-ACK-ACS712-RAIL-20261023-01", "ID": "000001",
    }
    controller.ARM_ACK_TIMEOUT_SEC = 0.02
    return controller, fake


def assert_no_drive_writes(fake):
    assert not any(
        command in ("FWD", "REV", "START", "RESUME")
        or (command.startswith("PWM=") and command != "PWM=0")
        or command.startswith(("FWD@", "REV@", "START@", "RESUME@", "PWM="))
        and not command.startswith("PWM=0")
        for command in fake.writes
    )


def test_exact_fresh_arm_ack_authorizes_tagged_drive_only_after_ack(monkeypatch):
    controller, fake = make_controller(monkeypatch, arm_responses=lambda f, token: f.lines.append(f"ARMED,{token}\n".encode()))
    assert controller.forward() is False
    assert controller.reverse() is False
    assert controller.set_pwm(35) is False
    assert fake.writes == []
    assert controller.arm() is True
    assert fake.writes[0] == "ARM=A1B2C3D4"
    assert controller._active_arm_token == "A1B2C3D4"
    assert controller.forward() == "FWD"
    assert fake.writes[-1] == "FWD@A1B2C3D4"


@pytest.mark.parametrize("responses", [
    None,
    ["OK"],
    ["ARMED,DEADBEEF"],
    ["ARMED,A1B2C3D"],
    ["not-an-ack"],
])
def test_missing_malformed_or_stale_arm_ack_fails_closed(monkeypatch, responses):
    controller, fake = make_controller(monkeypatch, arm_responses=responses)
    assert controller.arm() is False
    assert controller._active_arm_token is None
    assert controller._stop_requested()
    assert "PWM=0" in fake.writes
    assert "STOP" in fake.writes
    assert_no_drive_writes(fake)


def test_arm_required_response_fails_closed_and_attempts_stop(monkeypatch):
    controller, fake = make_controller(monkeypatch, arm_responses=["ERROR,ARM_REQUIRED"])
    assert controller.arm() is False
    assert controller._active_arm_token is None
    assert controller._stop_requested()
    assert "PWM=0" in fake.writes
    assert "STOP" in fake.writes
    assert_no_drive_writes(fake)


def test_disconnect_during_arm_never_authorizes_drive(monkeypatch):
    controller, fake = make_controller(monkeypatch, disconnect_on_arm=True)
    assert controller.arm() is False
    assert controller._active_arm_token is None
    assert controller.forward() is False
    assert_no_drive_writes(fake)


def test_preexisting_stop_latch_cannot_be_cleared_by_arm_ack(monkeypatch):
    controller, fake = make_controller(monkeypatch, arm_responses=lambda f, token: f.lines.append(f"ARMED,{token}\n".encode()))
    controller._emergency_stop_latched = True
    controller._ensure_stop_event().set()
    assert controller.arm() is False
    assert controller._stop_requested()
    assert controller._active_arm_token is None
    assert not any(command.startswith("ARM=") for command in fake.writes)
    assert_no_drive_writes(fake)


def test_late_arm_ack_after_stop_generation_change_cannot_authorize(monkeypatch):
    controller, fake = make_controller(monkeypatch, arm_responses=lambda f, token: f.lines.append(f"ARMED,{token}\n".encode()))

    def ack_but_stop_raced(expected, timeout):
        # Models emergency_stop publishing its generation/latch while ARM waits
        # for the serial response and before the ACK is consumed by arm().
        controller._emergency_stop_generation += 1
        controller._ensure_stop_event().set()
        return True

    controller._wait_for_command_ack = ack_but_stop_raced
    assert controller.arm() is False
    assert controller._active_arm_token is None
    assert controller._stop_requested()
    assert_no_drive_writes(fake)


def test_arm_required_during_run_latches_stop_before_any_further_drive(monkeypatch):
    controller, fake = make_controller(monkeypatch, arm_responses=lambda f, token: f.lines.append(f"ARMED,{token}\n".encode()))
    assert controller.arm() is True
    fake.lines.append(b"ERROR,ARM_REQUIRED\n")
    assert controller.read_measurement() is None
    assert controller._stop_requested()
    assert controller._active_arm_token is None
    assert "STOP" in fake.writes
    assert controller.forward() is False
    assert_no_drive_writes(fake)
