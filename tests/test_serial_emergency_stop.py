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


def test_controller_stop_during_port_open_cannot_be_followed_by_late_reconnect(monkeypatch):
    import threading
    import communication.serial_controller as serial_controller_module

    open_entered = threading.Event()
    release_open = threading.Event()
    opened_handles = []

    class FakeSerial:
        def __init__(self, *args, **kwargs):
            open_entered.set()
            assert release_open.wait(timeout=3)
            self.writes = []
            self.closed = False
            self.timeout = kwargs.get("timeout", 1)
            opened_handles.append(self)

        def reset_input_buffer(self):
            pass

        def reset_output_buffer(self):
            pass

        @property
        def in_waiting(self):
            return 0

        def write(self, data):
            self.writes.append(data)

        def close(self):
            self.closed = True

    class FakeSerialModule:
        Serial = FakeSerial

    monkeypatch.setattr(serial_controller_module, "serial", FakeSerialModule)
    monkeypatch.setattr(serial_controller_module.time, "sleep", lambda *_: None)

    controller = SerialController()
    controller._verify_info_response = lambda timeout=1.0: False
    connect_result = {}
    connect_thread = threading.Thread(target=lambda: connect_result.update(ok=controller.connect()))
    connect_thread.start()
    assert open_entered.wait(timeout=2)

    stop_started = threading.Event()
    original_stop = controller.emergency_stop

    def marked_stop():
        stop_started.set()
        return original_stop()

    controller.emergency_stop = marked_stop
    stop_result = {}
    stop_thread = threading.Thread(target=lambda: stop_result.update(result=controller.emergency_stop()))
    stop_thread.start()
    assert stop_started.wait(timeout=2)

    # Release the port-open call only after STOP has attempted to begin.
    # The lifecycle lock must make STOP run after connect cleanup/completion.
    release_open.set()
    connect_thread.join(timeout=3)
    stop_thread.join(timeout=3)

    assert not connect_thread.is_alive()
    assert not stop_thread.is_alive()
    assert connect_result["ok"] is True  # Port connectivity is distinct from INFO identity.
    assert stop_result["result"]["stop_command"] is True  # Safe STOP remains available while identity is unverified.
    assert opened_handles[0].closed is True
    assert opened_handles[0].writes == [b"INFO\n", b"PWM=0\n", b"STOP\n"]
    assert controller._emergency_stop_latched is True
    assert controller.serial is None
    assert controller.connected is False
    assert controller.identity_verified is False


def test_serial_manager_disconnect_clears_state_and_reports_close_exception():
    from communication.serial_manager import SerialManager

    class CloseFailure:
        is_open = True

        def close(self):
            raise OSError("close failed")

    manager = SerialManager()
    errors = []
    disconnected = []
    manager.error.connect(errors.append)
    manager.disconnected.connect(lambda: disconnected.append(True))
    manager.serial = CloseFailure()

    result = manager.disconnect()

    assert result is False
    assert manager.serial is None
    assert manager.reader is None
    assert disconnected == [True]
    assert any("serial close" in error and "close failed" in error for error in errors)


def test_serial_manager_emergency_stop_reports_close_failure():
    from communication.serial_manager import SerialManager

    class CloseFailure:
        is_open = True

        def __init__(self):
            self.writes = []

        def write(self, data):
            self.writes.append(data)

        def close(self):
            raise OSError("close failed")

    manager = SerialManager()
    fake = CloseFailure()
    manager.serial = fake
    result = manager.emergency_stop()

    assert fake.writes == [b"PWM=0\n", b"STOP\n"]
    assert result["pwm_zero"] is True
    assert result["stop_command"] is True
    assert result["disconnect"] is False
    assert any("disconnect" in error and "cleanup" in error for error in result["errors"])
    assert manager.serial is None
    assert manager._emergency_stop_latched is True

def test_ui_motor_disconnect_uses_latched_emergency_stop_for_connected_controller():
    from types import SimpleNamespace
    from app.main import MainWindow

    events = []

    class FakeController:
        connected = True

        def stop_breakin(self):
            events.append("unsafe_plain_stop")

        def disconnect(self):
            events.append("plain_disconnect")

    class FakeLabel:
        def __init__(self):
            self.value = None

        def setText(self, value):
            self.value = value

    class FakeButton:
        def __init__(self):
            self.enabled = None

        def setEnabled(self, enabled):
            self.enabled = enabled

    controller = FakeController()
    ui = SimpleNamespace(
        _motor_controller=lambda: controller,
        stop_run=lambda: events.append("latched_emergency_stop"),
        motor_serial_status=FakeLabel(),
        motor_connect=FakeButton(),
        motor_disconnect=FakeButton(),
        _stop_latched=True,
        _log_event=lambda message: events.append(message),
    )

    MainWindow.disconnect_motor_serial(ui)

    assert events[0] == "latched_emergency_stop"
    assert "unsafe_plain_stop" not in events
    assert "plain_disconnect" not in events
    assert ui.motor_serial_status.value == "MOTOR: DISCONNECTED  /dev/ttyACM0"
    assert ui.motor_connect.enabled is False
    assert ui.motor_disconnect.enabled is False

