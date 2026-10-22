"""Regression tests for ordered firmware acknowledgements during emergency STOP."""

from communication.serial_manager import SerialManager


def test_command_response_is_ignored_when_no_stop_ack_is_pending():
    manager = SerialManager()

    manager._observe_identity({"record_type": "COMMAND_RESPONSE", "value": "OK"})

    assert not manager._stop_response_event.is_set()

    manager._pending_stop_command = "STOP#NEWNONCE"
    manager._awaiting_stop_response = True
    manager._observe_identity({"record_type": "COMMAND_RESPONSE", "value": "OK,STOP#OLDNONCE"})
    assert not manager._stop_response_event.is_set()


def test_pwm_zero_and_stop_acknowledgements_are_correlated_in_order(monkeypatch):
    manager = SerialManager()

    def send_and_ack(command):
        if command.startswith("PWM=0#") or command.startswith("STOP#"):
            manager._observe_identity({"record_type": "COMMAND_RESPONSE", "value": "OK," + command})
            return True
        return False

    monkeypatch.setattr(manager, "send", send_and_ack)
    monkeypatch.setattr(manager, "disconnect", lambda: True)

    result = manager.emergency_stop()

    assert result["pwm_zero"] is True
    assert result["pwm_zero_ack"] is True
    assert result["stop_command"] is True
    assert result["stop_ack"] is True
    assert result["disconnect"] is True


def test_stop_ack_is_not_claimed_when_pwm_zero_ack_is_missing(monkeypatch):
    manager = SerialManager()

    def send_with_missing_pwm_ack(command):
        if command.startswith("STOP#"):
            # Even a correctly correlated STOP ACK cannot compensate for the
            # missing PWM=0 ACK: the full two-step handshake is incomplete.
            manager._observe_identity({"record_type": "COMMAND_RESPONSE", "value": "OK," + command})
            return True
        if command.startswith("PWM=0#"):
            return True
        return False

    monkeypatch.setattr(manager, "send", send_with_missing_pwm_ack)
    monkeypatch.setattr(manager, "disconnect", lambda: True)

    result = manager.emergency_stop()

    assert result["pwm_zero"] is True
    assert result["pwm_zero_ack"] is False
    assert result["stop_command"] is True
    assert result["stop_ack"] is False
    assert any("PWM=0 nonce-correlated firmware ACK not received" in error for error in result["errors"])



def test_legacy_stop_commands_are_sent_as_fallback_without_counting_plain_ok(monkeypatch):
    manager = SerialManager()
    sent_commands = []

    def legacy_compatible_send(command):
        sent_commands.append(command)
        # Simulate an older firmware: it accepts legacy commands but does not
        # understand the nonce-bearing extension and never echoes a nonce.
        return command in ("PWM=0", "STOP")

    monkeypatch.setattr(manager, "send", legacy_compatible_send)
    monkeypatch.setattr(manager, "disconnect", lambda: True)

    result = manager.emergency_stop()

    assert any(command.startswith("PWM=0#") for command in sent_commands)
    assert "PWM=0" in sent_commands
    assert any(command.startswith("STOP#") for command in sent_commands)
    assert "STOP" in sent_commands
    assert result["pwm_zero"] is True
    assert result["stop_command"] is True
    assert result["pwm_zero_ack"] is False
    assert result["stop_ack"] is False
