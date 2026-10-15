from types import SimpleNamespace

import communication.serial_controller as serial_module
from communication.serial_controller import SerialController
import app.main as main_module


class FakeLabel:
    def __init__(self):
        self.text = ""

    def setText(self, value):
        self.text = value


class FakeButton:
    def __init__(self):
        self.enabled = True

    def setEnabled(self, value):
        self.enabled = bool(value)


class InfoPort:
    def __init__(self, info_line=None):
        self.info_line = info_line
        self.lines = []
        self.writes = []
        self.timeout = 1.0
        self.closed = False

    def write(self, data):
        self.writes.append(data)
        if data == b"INFO\n" and self.info_line is not None:
            self.lines.append(self.info_line.encode("utf-8"))
        return len(data)

    def readline(self):
        return self.lines.pop(0) if self.lines else b""

    @property
    def in_waiting(self):
        return len(self.lines)

    def reset_input_buffer(self):
        self.lines.clear()

    def reset_output_buffer(self):
        self.writes.clear()

    def close(self):
        self.closed = True


def make_window(controller):
    return SimpleNamespace(
        _motor_controller=lambda: controller,
        motor_serial_status=FakeLabel(),
        motor_connect=FakeButton(),
        motor_disconnect=FakeButton(),
        sequence_status=FakeLabel(),
    )


def test_real_serial_controller_info_handshake_updates_main_ui(monkeypatch):
    info = "INFO,TYPE=MOTOR,MODEL=MOTOR_BREAKIN_V3,FW=3.00,BUILD=TEST,ID=000001\n"
    port = InfoPort(info)
    monkeypatch.setattr(serial_module, "serial", SimpleNamespace(Serial=lambda *a, **k: port))
    monkeypatch.setattr(serial_module.time, "sleep", lambda _seconds: None)
    controller = SerialController()
    window = make_window(controller)

    main_module.MainWindow.connect_motor_serial(window)

    assert controller.connected is True
    assert controller.identified is True
    assert "CONNECTED / IDENTIFIED" in window.motor_serial_status.text
    assert window.motor_connect.enabled is False
    assert window.motor_disconnect.enabled is True


def test_real_serial_controller_invalid_info_updates_main_ui(monkeypatch):
    malformed = "INFO,TYPE=BATTERY,MODEL=MOTOR_BREAKIN_V3,FW=3.00,BUILD=TEST,ID=000001\n"
    port = InfoPort(malformed)
    monkeypatch.setattr(serial_module, "serial", SimpleNamespace(Serial=lambda *a, **k: port))
    monkeypatch.setattr(serial_module.time, "sleep", lambda _seconds: None)
    controller = SerialController()
    window = make_window(controller)

    main_module.MainWindow.connect_motor_serial(window)

    assert controller.connected is True
    assert controller.identified is False
    assert "IDENTITY UNCONFIRMED" in window.motor_serial_status.text
    assert "Unsupported device TYPE" in window.motor_serial_status.text
    assert window.motor_connect.enabled is False
    assert window.motor_disconnect.enabled is True


def test_real_serial_controller_info_timeout_updates_main_ui(monkeypatch):
    port = InfoPort()
    monkeypatch.setattr(serial_module, "serial", SimpleNamespace(Serial=lambda *a, **k: port))
    monkeypatch.setattr(serial_module.time, "sleep", lambda _seconds: None)
    controller = SerialController()
    controller.INFO_TIMEOUT_SEC = 0.01
    window = make_window(controller)

    main_module.MainWindow.connect_motor_serial(window)

    assert controller.connected is True
    assert controller.identified is False
    assert "IDENTITY UNCONFIRMED" in window.motor_serial_status.text
    assert "info_timeout" in window.motor_serial_status.text
