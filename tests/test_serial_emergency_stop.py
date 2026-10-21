from communication.serial_controller import SerialController


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
