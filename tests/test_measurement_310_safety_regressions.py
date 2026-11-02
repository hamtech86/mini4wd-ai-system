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
