from communication.serial_controller import SerialController
from communication.serial_manager import SerialManager


def test_emergency_stop_attempts_stop_and_disconnect_if_pwm_zero_raises():
    controller = SerialController.__new__(SerialController)
    calls = []

    def set_pwm(value):
        calls.append(("pwm", value))
        raise OSError("PWM write failed")

    def send_command(command):
        calls.append(("command", command))
        return "STOP"

    def disconnect():
        calls.append(("disconnect", None))

    controller.set_pwm = set_pwm
    controller.send_command = send_command
    controller.disconnect = disconnect

    result = controller.emergency_stop()

    assert calls == [("pwm", 0), ("command", "STOP"), ("disconnect", None)]
    assert result["pwm_zero"] is False
    assert result["stop_command"] is True
    assert result["disconnect"] is True
    assert any("PWM write failed" in error for error in result["errors"])


def test_emergency_stop_attempts_disconnect_if_stop_command_raises():
    controller = SerialController.__new__(SerialController)
    calls = []

    def set_pwm(value):
        calls.append(("pwm", value))
        return "PWM=0"

    def send_command(command):
        calls.append(("command", command))
        raise OSError("STOP write failed")

    def disconnect():
        calls.append(("disconnect", None))

    controller.set_pwm = set_pwm
    controller.send_command = send_command
    controller.disconnect = disconnect

    result = controller.emergency_stop()

    assert calls == [("pwm", 0), ("command", "STOP"), ("disconnect", None)]
    assert result["pwm_zero"] is True
    assert result["stop_command"] is False
    assert result["disconnect"] is True
    assert any("STOP write failed" in error for error in result["errors"])



def test_disconnect_clears_state_even_when_close_raises():
    class CloseFailure:
        def close(self):
            raise OSError("close failed")

    controller = SerialController()
    controller.serial = CloseFailure()
    controller.connected = True
    controller.identity_verified = True
    controller.device_info = {"MODEL": "MOTOR_BREAKIN_V3"}

    try:
        controller.disconnect()
    except OSError:
        pass

    assert controller.serial is None
    assert controller.connected is False
    assert controller.identity_verified is False
    assert controller.device_info is None


def test_emergency_stop_latches_late_drive_commands_even_after_identity_is_reasserted():
    class FakeSerial:
        def __init__(self):
            self.writes = []
            self.closed = False

        def write(self, data):
            self.writes.append(data)

        def close(self):
            self.closed = True

    controller = SerialController()
    first = FakeSerial()
    controller.serial = first
    controller.connected = True
    controller.identity_verified = True

    result = controller.emergency_stop()

    assert result["pwm_zero"] is True
    assert result["stop_command"] is True
    assert result["disconnect"] is True
    assert first.writes == [b"PWM=0\n", b"STOP\n"]
    assert first.closed is True

    # Simulate a stale worker trying to reuse/reconnect the same controller
    # after STOP. Even if identity is mistakenly marked verified, drive
    # commands must remain blocked for this application-session object.
    second = FakeSerial()
    controller.serial = second
    controller.connected = True
    controller.identity_verified = True

    assert controller.send_command("FWD") is False
    assert controller.send_command("REV") is False
    assert controller.send_command("START") is False
    assert controller.send_command("RESUME") is False
    assert controller.set_pwm(80) is False
    assert second.writes == []

    # Safe stop commands remain available after the latch.
    assert controller.set_pwm(0) == "PWM=0"
    assert controller.send_command("STOP") == "STOP"
    assert second.writes == [b"PWM=0\n", b"STOP\n"]


def test_emergency_stop_serializes_with_an_in_flight_positive_pwm_write():
    import threading

    class BlockingSerial:
        def __init__(self):
            self.writes = []
            self.entered_positive_write = threading.Event()
            self.release_positive_write = threading.Event()
            self.closed = False

        def write(self, data):
            self.writes.append(data)
            if data == b"PWM=80\n":
                self.entered_positive_write.set()
                assert self.release_positive_write.wait(timeout=2)

        def close(self):
            self.closed = True

    controller = SerialController()
    fake = BlockingSerial()
    controller.serial = fake
    controller.connected = True
    controller.identity_verified = True

    drive_thread = threading.Thread(target=lambda: controller.set_pwm(80))
    drive_thread.start()
    assert fake.entered_positive_write.wait(timeout=2)

    stop_result = {}
    stop_thread = threading.Thread(target=lambda: stop_result.update(controller.emergency_stop()))
    stop_thread.start()

    # Let the already-started write finish; STOP must then be the final drive
    # command, and later commands must be rejected by the latch.
    fake.release_positive_write.set()
    drive_thread.join(timeout=2)
    stop_thread.join(timeout=2)

    assert not drive_thread.is_alive()
    assert not stop_thread.is_alive()
    assert stop_result["pwm_zero"] is True
    assert stop_result["stop_command"] is True
    assert fake.writes[:3] == [b"PWM=80\n", b"PWM=0\n", b"STOP\n"]
    assert controller.send_command("PWM=90") is False
    assert fake.writes == [b"PWM=80\n", b"PWM=0\n", b"STOP\n"]


def test_active_serial_manager_latches_drive_commands_after_emergency_stop():
    class FakeSerial:
        def __init__(self):
            self.writes = []
            self.is_open = True

        def write(self, data):
            self.writes.append(data)

        def close(self):
            self.is_open = False

    manager = SerialManager()
    first = FakeSerial()
    manager.serial = first

    result = manager.emergency_stop()

    assert result["pwm_zero"] is True
    assert result["stop_command"] is True
    assert result["disconnect"] is True
    assert first.writes == [b"PWM=0\n", b"STOP\n"]
    assert not first.is_open

    # Simulate a stale worker attempting to reuse this manager after STOP.
    second = FakeSerial()
    manager.serial = second
    assert manager.send("FWD") is False
    assert manager.send("REV") is False
    assert manager.send("START") is False
    assert manager.send("RESUME") is False
    assert manager.send("PWM=80") is False
    assert second.writes == []

    # The safety commands remain available after the latch.
    assert manager.send("PWM=0") is True
    assert manager.send("STOP") is True
    assert second.writes == [b"PWM=0\n", b"STOP\n"]


def test_active_serial_manager_orders_emergency_stop_after_in_flight_write():
    import threading

    class BlockingSerial:
        def __init__(self):
            self.writes = []
            self.is_open = True
            self.entered = threading.Event()
            self.release = threading.Event()

        def write(self, data):
            self.writes.append(data)
            if data == b"PWM=80\n":
                self.entered.set()
                assert self.release.wait(timeout=2)

        def close(self):
            self.is_open = False

    manager = SerialManager()
    fake = BlockingSerial()
    manager.serial = fake

    drive_thread = threading.Thread(target=lambda: manager.send("PWM=80"))
    drive_thread.start()
    assert fake.entered.wait(timeout=2)

    stop_result = {}
    stop_thread = threading.Thread(target=lambda: stop_result.update(manager.emergency_stop()))
    stop_thread.start()
    fake.release.set()

    drive_thread.join(timeout=2)
    stop_thread.join(timeout=2)

    assert not drive_thread.is_alive()
    assert not stop_thread.is_alive()
    assert stop_result["pwm_zero"] is True
    assert stop_result["stop_command"] is True
    assert fake.writes[:3] == [b"PWM=80\n", b"PWM=0\n", b"STOP\n"]
    assert manager.send("PWM=90") is False
    assert fake.writes == [b"PWM=80\n", b"PWM=0\n", b"STOP\n"]
