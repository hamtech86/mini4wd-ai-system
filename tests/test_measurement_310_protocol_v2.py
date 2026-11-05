import struct
import uuid

import pytest

from measurement_310.protocol_v2 import (
    ADC_BATCH_SIZE, HEADER_SIZE, PROTOCOL_V2_MAGIC, PROTOCOL_V2_VERSION,
    MessageType, ProtocolV2Codec, ProtocolV2Error,
)

SESSION = "12345678-1234-5678-9abc-def012345678"
CODEC = ProtocolV2Codec(PROTOCOL_V2_MAGIC, PROTOCOL_V2_VERSION)


def decode(frame):
    return CODEC.decode(frame).message


def test_v2_header_is_29_bytes_and_transmits_full_uuid():
    frame = CODEC.encode_hello(session_id=SESSION, host_nonce64=0x0102030405060708)
    decoded = CODEC.decode(frame)
    assert HEADER_SIZE == 29
    assert decoded.message["measurement_session_id"] == SESSION
    assert decoded.message["host_nonce64"] == 0x0102030405060708
    raw = __import__("measurement_310.protocol_v1", fromlist=["cobs_decode"]).cobs_decode(frame[:-1])
    assert raw[5:21] == uuid.UUID(SESSION).bytes


def test_v1_frame_is_rejected_by_v2_codec():
    from measurement_310.protocol_v1 import ProtocolV1Codec, PROTOCOL_V1_MAGIC, PROTOCOL_V1_VERSION
    old = ProtocolV1Codec(PROTOCOL_V1_MAGIC, PROTOCOL_V1_VERSION)
    frame = old.encode_hello(session_tag=1, host_nonce64=7)
    with pytest.raises((ProtocolV2Error, ValueError)):
        CODEC.decode(frame)


def test_hello_ack_carries_device_owned_next_sequence():
    payload = struct.pack("<BQQQ", 0, 0x123456789ABCDEF0, 55, 0x100000002)
    frame = CODEC.encode_message(MessageType.HELLO_ACK, session_id=SESSION,
                                 epoch_tag=0x9ABCDEF0, payload=payload)
    msg = decode(frame)
    assert msg["boot_id64"] == 0x123456789ABCDEF0
    assert msg["next_sample_sequence64"] == 0x100000002


def test_hello_ack_rejects_zero_boot_for_success():
    payload = struct.pack("<BQQQ", 0, 0, 55, 0)
    with pytest.raises(ProtocolV2Error):
        CODEC.encode_message(MessageType.HELLO_ACK, session_id=SESSION,
                             epoch_tag=0, payload=payload)


def test_adc_batch_full_width_sequence_and_188_byte_wire_limit():
    first = 0x100000001
    payload = bytearray(struct.pack("<QBBB", first, 0, 12, 0))
    for i in range(12):
        payload.extend(struct.pack("<IBHHBH", 1000 + i, i % 6, 500, i + 1, 0, 0))
    assert len(payload) == ADC_BATCH_SIZE == 155
    frame = CODEC.encode_message(MessageType.ADC_BATCH, session_id=SESSION,
                                 epoch_tag=1, payload=bytes(payload))
    msg = decode(frame)
    assert [s["sample_sequence64"] for s in msg["samples"]] == list(range(first, first + 12))
    assert len(frame) <= 188


def test_adc_batch_failed_attempt_consumes_sequence_slot():
    payload = bytearray(struct.pack("<QBBB", 99, 0, 12, 0))
    for i in range(12):
        status = 2 if i == 3 else 0
        raw = 0xFFFF if status else 512
        payload.extend(struct.pack("<IBHHBH", i, i % 6, raw, 1, status, 0))
    msg = decode(CODEC.encode_message(MessageType.ADC_BATCH, session_id=SESSION,
                                      epoch_tag=1, payload=bytes(payload)))
    assert msg["samples"][3]["sample_sequence64"] == 102
    assert msg["samples"][3]["acquisition_status"] == 2


def test_adc_batch_rejects_uint64_sequence_wrap():
    payload = bytearray(struct.pack("<QBBB", 0xFFFFFFFFFFFFFFF8, 0, 12, 0))
    for i in range(12):
        payload.extend(struct.pack("<IBHHBH", i, i % 6, 512, 1, 0, 0))
    with pytest.raises(ProtocolV2Error):
        CODEC.encode_message(MessageType.ADC_BATCH, session_id=SESSION,
                             epoch_tag=1, payload=bytes(payload))


def test_status_uses_uint64_next_sequence():
    payload = struct.pack("<BBHIQ", 2, 7, 3, 9, 0x100000001)
    msg = decode(CODEC.encode_message(MessageType.STATUS, session_id=SESSION,
                                      epoch_tag=1, payload=payload))
    assert msg["next_sample_sequence64"] == 0x100000001


@pytest.mark.parametrize("bad", ["", "not-a-uuid", "00000000-0000-0000-0000-000000000000"])
def test_hello_rejects_invalid_or_zero_session_uuid(bad):
    with pytest.raises((ProtocolV2Error, ValueError)):
        CODEC.encode_hello(session_id=bad, host_nonce64=1)


def test_uuid_byte_order_is_rfc4122_network_order():
    raw = uuid.UUID(SESSION).bytes
    assert raw.hex() == "12345678123456789abcdef012345678"


def test_protocol_version_is_normative():
    with pytest.raises(ValueError):
        ProtocolV2Codec(PROTOCOL_V2_MAGIC, 1)
    with pytest.raises(ValueError):
        ProtocolV2Codec(0x1234, PROTOCOL_V2_VERSION)


def test_adc_batch_can_reach_but_not_consume_uint64_exhaustion_sentinel():
    first = 0xFFFFFFFFFFFFFFFF - 12
    payload = bytearray(struct.pack("<QBBB", first, 0, 12, 0))
    for i in range(12):
        payload.extend(struct.pack("<IBHHBH", i, i % 6, 512, 1, 0, 0))
    msg = decode(CODEC.encode_message(
        MessageType.ADC_BATCH, session_id=SESSION, epoch_tag=1, payload=bytes(payload)
    ))
    assert msg["samples"][-1]["sample_sequence64"] == 0xFFFFFFFFFFFFFFFE

    first = 0xFFFFFFFFFFFFFFFF - 11
    payload = bytearray(struct.pack("<QBBB", first, 0, 12, 0))
    for i in range(12):
        payload.extend(struct.pack("<IBHHBH", i, i % 6, 512, 1, 0, 0))
    with pytest.raises(ProtocolV2Error):
        CODEC.encode_message(
            MessageType.ADC_BATCH, session_id=SESSION, epoch_tag=1, payload=bytes(payload)
        )
