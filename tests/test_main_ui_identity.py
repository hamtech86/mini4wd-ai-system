from types import SimpleNamespace

import pytest

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


class FakeMotorController:
    def __init__(self, *, identified, identity_error=None, connect_result=True):
        self.connected = False
        self.identified = identified
        self.identity_error = identity_error
        self.connect_result = connect_result
        self.disconnect_called = False
        self.stop_called = False

    def connect(self):
        self.connected = self.connect_result
        return self.connect_result

    def require_identified_device(self):
        if not self.identified or not self.connected:
            raise RuntimeError(
                f"Motor device is not identified: {self.identity_error or 'device identity is unconfirmed'}"
            )

    def stop_breakin(self):
        self.stop_called = True

    def disconnect(self):
        self.disconnect_called = True
        self.connected = False
        self.identified = False
        self.identity_error = "disconnected"


def fake_window(controller):
    return SimpleNamespace(
        _motor_controller=lambda: controller,
        motor_serial_status=FakeLabel(),
        motor_connect=FakeButton(),
        motor_disconnect=FakeButton(),
        sequence_status=FakeLabel(),
    )


def test_successful_connection_displays_identified_state():
    controller = FakeMotorController(identified=True)
    window = fake_window(controller)

    main_module.MainWindow.connect_motor_serial(window)

    assert "CONNECTED" in window.motor_serial_status.text
    assert "IDENTIFIED" in window.motor_serial_status.text
    assert window.motor_connect.enabled is False
    assert window.motor_disconnect.enabled is True


@pytest.mark.parametrize(
    ("identity_error", "expected_reason"),
    [
        ("Malformed INFO response", "Malformed INFO response"),
        ("info_timeout", "info_timeout"),
    ],
)
def test_open_serial_port_without_valid_info_displays_unconfirmed_state(
    identity_error, expected_reason
):
    controller = FakeMotorController(
        identified=False,
        identity_error=identity_error,
        connect_result=True,
    )
    window = fake_window(controller)

    main_module.MainWindow.connect_motor_serial(window)

    assert "CONNECTED" in window.motor_serial_status.text
    assert "IDENTITY UNCONFIRMED" in window.motor_serial_status.text
    assert expected_reason in window.motor_serial_status.text
    assert window.motor_connect.enabled is False
    assert window.motor_disconnect.enabled is True


@pytest.mark.parametrize("operation", ["Benchmark", "Sequence"])
def test_unidentified_device_refuses_start_and_explains_why(monkeypatch, operation):
    controller = FakeMotorController(
        identified=False,
        identity_error="info_timeout",
    )
    window = fake_window(controller)
    warnings = []
    monkeypatch.setattr(
        main_module.QMessageBox,
        "warning",
        lambda *args: warnings.append(args),
    )

    allowed = main_module.MainWindow._require_motor_identity(window, operation)

    assert allowed is False
    assert "開始拒否" in window.sequence_status.text
    assert "info_timeout" in window.sequence_status.text
    assert len(warnings) == 1
    assert controller.stop_called is False


def test_disconnect_clears_identity_and_restores_connect_controls():
    controller = FakeMotorController(identified=True)
    controller.connected = True
    window = fake_window(controller)

    main_module.MainWindow.disconnect_motor_serial(window)

    assert controller.disconnect_called is True
    assert controller.identified is False
    assert controller.connected is False
    assert "DISCONNECTED" in window.motor_serial_status.text
    assert window.motor_connect.enabled is True
    assert window.motor_disconnect.enabled is False
