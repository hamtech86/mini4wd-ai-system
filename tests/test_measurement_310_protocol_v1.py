import struct

import pytest

from measurement_310.protocol_v1 import (
    HEADER, MessageType, ProtocolV1Codec, ProtocolV1Error, PROTOCOL_V1_MAGIC, PROTOCOL_V1_VERSION, StopReason,
    cobs_decode, cobs_encode, crc16_ccitt_false, epoch_tag_for_boot_id,
)
from measurement_310.transport import DecodedFrame, IncompleteMessage


# Normative 310-4 v0.5 production constants, assigned by command authority.
MAGIC_FIXTURE = PROTOCOL_V1_MAGIC
VERSION_FIXTURE = PROTOCOL_V1_VERSION


@pytest.fixture
def codec():
    return ProtocolV1Codec(magic=MAGIC_FIXTURE, protocol_version=VERSION_FIXTURE)


def test_crc16_ccitt_false_check_value():
    assert crc16_ccitt_false(b"123456789") == 0x29B1


@pytest.mark.parametrize("payload", [
    b"", b"\x00", b"\x01", b"abc", bytes(range(1, 255)),
    b"\x00".join([b"a" * 253, b"b" * 254, b"c"]),
])
def test_cobs_round_trip(payload):
    assert cobs_decode(cobs_encode(payload)) == payload


def test_codec_requires_explicit_magic_and_version():
    with pytest.raises(TypeError):
        ProtocolV1Codec()
    with pytest.raises(ValueError):
        ProtocolV1Codec(magic=-1, protocol_version=VERSION_FIXTURE)
    with pytest.raises(ValueError):
        ProtocolV1Codec(magic=MAGIC_FIXTURE, protocol_version=256)
    with pytest.raises(ValueError, match="normative v1 value"):
        ProtocolV1Codec(magic=MAGIC_FIXTURE ^ 0x0001, protocol_version=VERSION_FIXTURE)
    with pytest.raises(ValueError, match="normative v1 value"):
        ProtocolV1Codec(magic=MAGIC_FIXTURE, protocol_version=VERSION_FIXTURE + 1)


def test_hello_frame_layout_crc_and_wire_length(codec):
    frame = codec.encode_hello(session_tag=0x10203040, host_nonce64=0x8877665544332211)
    assert frame.endswith(b"\x00")
    decoded = cobs_decode(frame[:-1])
    assert len(decoded) == 27
    assert len(frame) == 29
    magic, version, kind, flags, session, epoch, command = HEADER.unpack(decoded[:17])
    assert (magic, version, kind, flags, session, epoch, command) == (
        MAGIC_FIXTURE, VERSION_FIXTURE, MessageType.HELLO, 0, 0x10203040, 0, 0
    )
    assert struct.unpack("<Q", decoded[17:25])[0] == 0x8877665544332211
    assert struct.unpack("<H", decoded[-2:])[0] == crc16_ccitt_false(decoded[:-2])


def test_stream_decoder_handles_partial_and_multiple_frames(codec):
    first = codec.encode_hello(session_tag=10, host_nonce64=11)
    second = codec.encode_hello(session_tag=12, host_nonce64=13)
    with pytest.raises(IncompleteMessage):
        codec.decode(first[:-1])
    combined = first + second
    a = codec.decode(combined)
    assert isinstance(a, DecodedFrame)
    assert a.consumed_bytes == len(first)
    assert a.message["host_nonce64"] == 11
    b = codec.decode(combined[a.consumed_bytes:])
    assert b.consumed_bytes == len(second)
    assert b.message["host_nonce64"] == 13


def test_hello_ack_checks_full_boot_id_nonce_and_epoch_tag(codec):
    boot_id = 0x1234567800000000
    frame = codec.encode_message(
        MessageType.HELLO_ACK, session_tag=7,
        epoch_tag=epoch_tag_for_boot_id(boot_id), command_id=0,
        payload=struct.pack("<BQQ", 0, boot_id, 0xABCDEF),
    )
    message = codec.decode(frame).message
    assert message["boot_id64"] == boot_id
    assert message["echoed_host_nonce64"] == 0xABCDEF
    assert message["device_epoch_tag"] == 0xFFFFFFFF


def test_hello_ack_rejects_epoch_tag_not_derived_from_full_boot_id(codec):
    boot_id = 0x1234567800000001
    frame = codec.encode_message(
        MessageType.HELLO_ACK, session_tag=7, epoch_tag=0x12345678,
        command_id=0, payload=struct.pack("<BQQ", 0, boot_id, 9),
    )
    with pytest.raises(ProtocolV1Error, match="epoch tag"):
        codec.decode(frame)


def test_arm_and_pwm_set_exact_payloads(codec):
    arm = codec.encode_arm(session_tag=3, epoch_tag=4, command_id=1, stage_context_token=1)
    decoded_arm = cobs_decode(arm[:-1])
    assert len(decoded_arm) == 22
    assert struct.unpack("<HB", decoded_arm[17:20]) == (1, 0)
    pwm = codec.encode_pwm_set(session_tag=3, epoch_tag=4, command_id=2,
                               pwm=30, stage_context_token=31)
    message = codec.decode(pwm).message
    assert message["kind"] == "PWM_SET"
    assert message["pwm"] == 30
    assert message["stage_context_token"] == 31


@pytest.mark.parametrize("kwargs", [
    {"pwm": 31, "stage_context_token": 1},
    {"pwm": 1, "stage_context_token": 0},
])
def test_pwm_set_rejects_invalid_values(codec, kwargs):
    with pytest.raises(ProtocolV1Error):
        codec.encode_pwm_set(session_tag=3, epoch_tag=4, command_id=1, **kwargs)


def test_arm_requires_initial_pwm_zero_and_nonzero_context(codec):
    with pytest.raises(ProtocolV1Error):
        codec.encode_message(MessageType.ARM, session_tag=3, epoch_tag=4, command_id=1,
                             payload=struct.pack("<HB", 1, 1))
    with pytest.raises(ProtocolV1Error):
        codec.encode_arm(session_tag=3, epoch_tag=4, command_id=1, stage_context_token=0)


def test_ack_enum_and_rejected_pwm_rules(codec):
    with pytest.raises(ProtocolV1Error, match="applied_pwm"):
        codec.encode_message(
            MessageType.APPLY_ACK, session_tag=3, epoch_tag=4, command_id=1,
            payload=struct.pack("<BBH", 7, 2, 1),
        )
    with pytest.raises(ProtocolV1Error):
        codec.encode_message(
            MessageType.ARM_ACK, session_tag=3, epoch_tag=4, command_id=1,
            payload=struct.pack("<BBH", 0, 1, 0),
        )
    # A failed ARM may legitimately report no active context token.
    frame = codec.encode_message(
        MessageType.ARM_ACK, session_tag=3, epoch_tag=4, command_id=1,
        payload=struct.pack("<BBH", 1, 0, 0),
    )
    assert codec.decode(frame).message["active_context_token"] == 0


def test_stop_request_and_ack_layout(codec):
    request = codec.encode_stop_request(session_tag=9, epoch_tag=8, command_id=44,
                                        stop_reason=StopReason.ACK_TIMEOUT, stop_request_id=65535)
    decoded = cobs_decode(request[:-1])
    assert len(decoded) == 22
    assert struct.unpack("<BH", decoded[17:20]) == (2, 65535)
    ack = codec.encode_message(
        MessageType.STOP_ACK, session_tag=9, epoch_tag=8, command_id=44,
        payload=bytes([1, 3, 0]),
    )
    assert codec.decode(ack).message["request_outcome"] == 3


def test_adc_batch_fixed_length_and_sample_validation(codec):
    samples = b"".join(
        struct.pack("<HIBHHBH", i, 1000 + i, i % 6, 0 if i == 0 else 1023, 1, 0, 0)
        for i in range(12)
    )
    payload = struct.pack("<HBBB", 1, 0, 12, 0) + samples
    assert len(payload) == 173
    frame = codec.encode_message(MessageType.ADC_BATCH, session_tag=2, epoch_tag=3,
                                 command_id=0, payload=payload)
    assert len(cobs_decode(frame[:-1])) == 192
    assert codec.decode(frame).message["kind"] == "ADC_BATCH"


def test_crc_corruption_and_bad_header_are_rejected(codec):
    frame = bytearray(codec.encode_hello(session_tag=1, host_nonce64=2))
    frame[-2] ^= 0x01
    with pytest.raises(ProtocolV1Error, match="CRC"):
        codec.decode(frame)
    bad_header = HEADER.pack(MAGIC_FIXTURE, VERSION_FIXTURE, MessageType.HELLO, 1, 1, 0, 0)
    body = bad_header + struct.pack("<Q", 2)
    decoded = body + struct.pack("<H", crc16_ccitt_false(body))
    with pytest.raises(ProtocolV1Error, match="flags"):
        codec.decode(cobs_encode(decoded) + b"\x00")


def test_command_id_zero_rules_and_session_tag_are_enforced(codec):
    with pytest.raises(ProtocolV1Error):
        codec.encode_message(MessageType.PWM_SET, session_tag=1, epoch_tag=2,
                             command_id=0, payload=struct.pack("<BH", 1, 1))
    with pytest.raises(ProtocolV1Error):
        codec.encode_hello(session_tag=0, host_nonce64=1)


@pytest.mark.parametrize("invalid_reason,expected_error", [
    (0, "assigned StopReason"),
    (10, "assigned StopReason"),
    (254, "assigned StopReason"),
    (256, "uint8"),
    (True, "uint8"),
])
def test_codec_rejects_unassigned_stop_reason(invalid_reason, expected_error, codec):
    with pytest.raises(ProtocolV1Error, match=expected_error):
        codec.encode_stop_request(
            session_tag=0, epoch_tag=0, command_id=1,
            stop_reason=invalid_reason, stop_request_id=1,
        )


def test_stop_request_is_allowed_without_session_or_verified_epoch(codec):
    frame = codec.encode_stop_request(session_tag=0, epoch_tag=0, command_id=1,
                                      stop_reason=StopReason.OPERATOR_REQUEST, stop_request_id=1)
    message = codec.decode(frame).message
    assert message["kind"] == "STOP_REQ"
    assert message["measurement_session_tag"] == 0
    assert message["device_epoch_tag"] == 0


def test_failed_hello_ack_without_boot_identity_uses_zero_epoch_tag(codec):
    frame = codec.encode_message(
        MessageType.HELLO_ACK, session_tag=7, epoch_tag=0, command_id=0,
        payload=struct.pack("<BQQ", 1, 0, 123),
    )
    message = codec.decode(frame).message
    assert message["result"] == 1
    assert message["boot_id64"] == 0
    assert message["device_epoch_tag"] == 0


def test_failed_hello_ack_with_boot_identity_still_requires_matching_epoch_tag(codec):
    boot_id = 0x1234567800000001
    frame = codec.encode_message(
        MessageType.HELLO_ACK, session_tag=7, epoch_tag=0x12345678,
        command_id=0, payload=struct.pack("<BQQ", 2, boot_id, 123),
    )
    with pytest.raises(ProtocolV1Error, match="epoch tag"):
        codec.decode(frame)
