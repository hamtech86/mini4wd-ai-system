"""Host-side safety regressions for the protocol-neutral 310 transport.

These tests exercise only in-memory transports/codecs. They do not establish
physical STOP delivery, bounded UART latency, firmware behavior, or hardware safety.
"""
import pytest

from measurement_310.transport import (
    DecodedFrame,
    MockTransport,
    ProtocolClient,
    TransportError,
)


class OneFrameCodec:
    def encode_pwm(self, pwm):
        return bytes([pwm])

    def encode_stop(self):
        return b"STOP"

    def decode(self, payload):
        return {"kind": "PWM_ACK", "pwm": payload[0]}


def connected_client(codec=None, transport=None):
    transport = transport or MockTransport()
    client = ProtocolClient(transport, codec or OneFrameCodec())
    client.connect()
    return client, transport


@pytest.mark.parametrize("pwm", [-1, 31, True, 1.5])
def test_pwm_ack_out_of_domain_fails_closed(pwm):
    class InvalidAckCodec(OneFrameCodec):
        def decode(self, payload):
            return {"kind": "PWM_ACK", "pwm": pwm}

    client, transport = connected_client(InvalidAckCodec())
    transport.queue(b"ack")
    with pytest.raises(TransportError, match="invalid ACK PWM"):
        client.poll_ack()
    client.disconnect()


@pytest.mark.parametrize("consumed", [0, -1, 5, True])
def test_codec_invalid_consumed_length_is_rejected(consumed):
    class InvalidLengthCodec(OneFrameCodec):
        def decode(self, payload):
            return DecodedFrame({"kind": "PWM_ACK", "pwm": 3}, consumed)

    client, transport = connected_client(InvalidLengthCodec())
    transport.queue(b"abc")
    with pytest.raises(TransportError, match="invalid consumed byte count"):
        client.poll_ack()
    client.disconnect()


def test_receive_transport_failure_is_not_reported_as_empty_poll():
    client, transport = connected_client()
    transport.fail_receive = True
    with pytest.raises(TransportError, match="mock receive failure or disconnected"):
        client.poll_ack()
    client.disconnect()


def test_stop_send_failure_is_reported_as_failed_attempt_not_success():
    client, transport = connected_client()
    transport.fail_send = True
    with pytest.raises(TransportError, match="STOP command send failed"):
        client.send_stop()
    assert transport.sent == []
    client.disconnect()


def test_disconnect_discards_buffered_and_pending_protocol_messages():
    client, transport = connected_client()
    client._receive_buffer.extend(b"partial")
    client._pending_messages.append({"kind": "STATUS"})
    client._pending_acks.append((4, "2026-11-02T00:00:00.000Z"))
    client.disconnect()
    assert client._receive_buffer == bytearray()
    assert client._pending_messages == []
    assert client._pending_acks == []
    assert not client.connected

def test_duplicate_previous_stage_ack_fails_closed_after_next_pwm_send(tmp_path):
    """A delayed duplicate ACK from PWM N must not acknowledge PWM N+1."""
    from measurement_310.engine import SequenceController, SequenceState
    from raw_log_v2 import RawLogV2Writer

    class Clock:
        def __init__(self):
            self.ns = 1_000_000_000

        def monotonic_ns(self):
            return self.ns

        def utc_now(self):
            return "2026-11-02T00:00:00.000Z"

        def advance_ms(self, value):
            self.ns += value * 1_000_000

    clock = Clock()
    sent, stops = [], []
    acks = [(0, clock.utc_now())]

    manifest = {
        "log_id": "TEST-DUP-ACK", "measurement_session_id": "SESSION-DUP-ACK",
        "started_at_utc": clock.utc_now(), "motor_instance_id": None,
        "device": {"type": None, "model": None, "firmware_version": None,
                   "firmware_build": None, "firmware_id": None, "adc_resolution_bits": None},
        "measurement_conditions": {"direction": "UNKNOWN", "voltage_control_mode": "UNKNOWN",
            "sweep_pwm_min": 0, "sweep_pwm_max": 30, "stage_duration_ms": 10000,
            "schedule_owner": "PYTHON"},
    }
    ctl = SequenceController(
        RawLogV2Writer(tmp_path), manifest,
        lambda pwm: sent.append(pwm) or clock.utc_now(),
        lambda: stops.append("STOP"),
        lambda: acks.pop(0) if acks else None,
        clock,
    )
    ctl.startup_recover()
    ctl.start()
    assert ctl.poll() == SequenceState.RUNNING

    clock.advance_ms(10_000)
    assert ctl.poll() == SequenceState.WAITING_ACK
    assert sent == [0, 1]

    # The duplicate ACK for stage 0 arrives after PWM 1 has been sent.
    acks.append((0, clock.utc_now()))
    assert ctl.poll() == SequenceState.FAULT
    assert sent == [0, 1]
    assert stops == ["STOP"]

def test_late_ack_after_timeout_cannot_recover_faulted_sequence(tmp_path):
    """An ACK arriving after timeout must not revive or advance the sequence."""
    from measurement_310.engine import SequenceController, SequenceState
    from raw_log_v2 import RawLogV2Writer

    class Clock:
        def __init__(self):
            self.ns = 1_000_000_000

        def monotonic_ns(self):
            return self.ns

        def utc_now(self):
            return "2026-11-02T00:00:00.000Z"

        def advance_ms(self, value):
            self.ns += value * 1_000_000

    clock = Clock()
    sent, stops = [], []
    acks = []
    manifest = {
        "log_id": "TEST-LATE-ACK", "measurement_session_id": "SESSION-LATE-ACK",
        "started_at_utc": clock.utc_now(), "motor_instance_id": None,
        "device": {"type": None, "model": None, "firmware_version": None,
                   "firmware_build": None, "firmware_id": None, "adc_resolution_bits": None},
        "measurement_conditions": {"direction": "UNKNOWN", "voltage_control_mode": "UNKNOWN",
            "sweep_pwm_min": 0, "sweep_pwm_max": 30, "stage_duration_ms": 10000,
            "schedule_owner": "PYTHON"},
    }
    ctl = SequenceController(
        RawLogV2Writer(tmp_path), manifest,
        lambda pwm: sent.append(pwm) or clock.utc_now(),
        lambda: stops.append("STOP"),
        lambda: acks.pop(0) if acks else None,
        clock, ack_timeout_ms=100,
    )
    ctl.startup_recover()
    ctl.start()
    clock.advance_ms(100)
    assert ctl.poll() == SequenceState.FAULT
    assert sent == [0]
    assert stops == ["STOP"]

    # A late, otherwise matching ACK is now available to the controller.
    acks.append((0, clock.utc_now()))
    assert ctl.poll() == SequenceState.FAULT
    assert sent == [0]
    assert stops == ["STOP"]
    assert acks == [(0, clock.utc_now())]
