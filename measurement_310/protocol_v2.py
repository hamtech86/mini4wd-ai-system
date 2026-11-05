"""310 protocol v2 codec: full UUID session identity and device-owned uint64 samples."""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import struct
import uuid
from typing import Any

from .transport import DecodedFrame, IncompleteMessage
from .protocol_v1 import cobs_decode, cobs_encode, crc16_ccitt_false, epoch_tag_for_boot_id


class ProtocolV2Error(ValueError):
    pass


class MessageType(IntEnum):
    HELLO = 0x01
    HELLO_ACK = 0x02
    ARM = 0x03
    ARM_ACK = 0x04
    DISARM = 0x05
    DISARM_ACK = 0x06
    PWM_SET = 0x10
    APPLY_ACK = 0x11
    STOP_REQ = 0x20
    STOP_ACK = 0x21
    STATUS = 0x30
    ERROR = 0x31
    ADC_BATCH = 0x40


class DriveDirection(IntEnum):
    FWD = 0
    REV = 1


class StopReason(IntEnum):
    OPERATOR_REQUEST = 0x01
    ACK_TIMEOUT = 0x02
    ACK_IDENTITY_MISMATCH = 0x03
    COMMUNICATION_LOSS = 0x04
    EVIDENCE_DURABILITY_FAILURE = 0x05
    STAGE_DEADLINE_EXCEEDED = 0x06
    DEVICE_FAULT_REPORTED = 0x07
    HOST_PROCESS_SHUTDOWN = 0x08
    INTERNAL_HOST_FAULT = 0x09
    NORMAL_COMPLETION = 0x0A
    OTHER_UNCLASSIFIED = 0xFF


PROTOCOL_V2_MAGIC = 0x344D
PROTOCOL_V2_VERSION = 0x02
HEADER = struct.Struct("<HBBB16sII")
CRC = struct.Struct("<H")
HEADER_SIZE = 29
CRC_SIZE = 2
ADC_SAMPLE_SIZE = 12
ADC_BATCH_SIZE = 155

_STATE_NAMES = {
    0: "IDLE", 1: "ARMED", 2: "RUNNING", 3: "STOP_LATCHED",
    4: "STOPPED", 5: "FAULT", 6: "FAULT_STOP", 7: "BOOT_ID_INVALID",
}
_HELLO_RESULTS = {0, 1, 2, 3, 4}
_ARM_RESULTS = set(range(7))
_APPLY_RESULTS = set(range(9))
_STOP_RELATIONS = {0, 1, 2}
_STOP_OUTCOMES = {0, 1, 2, 3, 4}
_STOP_STATES = {0, 1, 2}
_ERROR_CODES = set(range(1, 15))
_ZERO_COMMAND_TYPES = {
    MessageType.HELLO, MessageType.HELLO_ACK, MessageType.STATUS,
    MessageType.ERROR, MessageType.ADC_BATCH,
}
_ZERO_SESSION_ALLOWED = {
    MessageType.STOP_REQ, MessageType.STOP_ACK, MessageType.STATUS, MessageType.ERROR,
}
_PAYLOAD_LENGTHS = {
    MessageType.HELLO: 8,
    MessageType.HELLO_ACK: 25,
    MessageType.ARM: 4,
    MessageType.ARM_ACK: 5,
    MessageType.DISARM: 2,
    MessageType.DISARM_ACK: 4,
    MessageType.PWM_SET: 3,
    MessageType.APPLY_ACK: 4,
    MessageType.STOP_REQ: 3,
    MessageType.STOP_ACK: 3,
    MessageType.STATUS: 16,
    MessageType.ERROR: 8,
    MessageType.ADC_BATCH: ADC_BATCH_SIZE,
}


def _uuid_bytes(value: str | uuid.UUID | bytes) -> bytes:
    if isinstance(value, bytes):
        raw = value
    else:
        try:
            raw = (value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))).bytes
        except (ValueError, TypeError, AttributeError) as exc:
            raise ProtocolV2Error("measurement_session_id must be a UUID") from exc
    if len(raw) != 16:
        raise ProtocolV2Error("measurement_session_id must contain exactly 16 UUID bytes")
    return raw


def _uuid_text(raw: bytes) -> str:
    return str(uuid.UUID(bytes=raw))


def _uint(value: int, bits: int, name: str, nonzero: bool = False) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < (1 << bits):
        raise ProtocolV2Error(f"{name} must be uint{bits}")
    if nonzero and value == 0:
        raise ProtocolV2Error(f"{name} must be nonzero")


@dataclass(frozen=True)
class ProtocolV2Codec:
    magic: int
    protocol_version: int

    def __post_init__(self):
        _uint(self.magic, 16, "magic")
        _uint(self.protocol_version, 8, "protocol_version")
        if self.magic != PROTOCOL_V2_MAGIC:
            raise ValueError(f"magic must equal normative v2 value 0x{PROTOCOL_V2_MAGIC:04X}")
        if self.protocol_version != PROTOCOL_V2_VERSION:
            raise ValueError(f"protocol_version must equal normative v2 value 0x{PROTOCOL_V2_VERSION:02X}")

    def _validate_header(self, kind: MessageType, session: bytes,
                         epoch_tag: int, command_id: int) -> None:
        _uint(epoch_tag, 32, "device_epoch_tag")
        _uint(command_id, 32, "command_id")
        if session == b"\x00" * 16 and kind not in _ZERO_SESSION_ALLOWED:
            raise ProtocolV2Error(f"{kind.name} requires nonzero measurement_session_id")
        if kind in _ZERO_COMMAND_TYPES:
            if command_id != 0:
                raise ProtocolV2Error(f"{kind.name} requires command_id=0")
        elif command_id == 0:
            raise ProtocolV2Error(f"{kind.name} requires nonzero command_id")
        if kind == MessageType.HELLO and epoch_tag != 0:
            raise ProtocolV2Error("HELLO requires device_epoch_tag=0")
        if kind not in {MessageType.HELLO, MessageType.HELLO_ACK, MessageType.STOP_REQ,
                        MessageType.STOP_ACK, MessageType.STATUS, MessageType.ERROR} and epoch_tag == 0:
            raise ProtocolV2Error(f"{kind.name} requires a verified nonzero epoch tag")

    def encode_message(self, message_type: MessageType | int, *,
                       session_id: str | uuid.UUID | bytes, epoch_tag: int,
                       command_id: int = 0, payload: bytes = b"") -> bytes:
        try:
            kind = MessageType(message_type)
        except ValueError as exc:
            raise ProtocolV2Error("unsupported message type") from exc
        session = _uuid_bytes(session_id)
        self._validate_header(kind, session, epoch_tag, command_id)
        if not isinstance(payload, bytes) or len(payload) != _PAYLOAD_LENGTHS[kind]:
            raise ProtocolV2Error(f"{kind.name} payload must be exactly {_PAYLOAD_LENGTHS[kind]} bytes")
        self._validate_payload(kind, payload)
        if kind == MessageType.HELLO_ACK:
            _result, boot_id64, _nonce, _next_sequence = struct.unpack("<BQQQ", payload)
            if boot_id64:
                if epoch_tag_for_boot_id(boot_id64) != epoch_tag:
                    raise ProtocolV2Error("HELLO_ACK epoch tag does not match full boot_id64")
            elif epoch_tag != 0:
                raise ProtocolV2Error("HELLO_ACK without valid boot identity requires epoch_tag=0")
        header = HEADER.pack(self.magic, self.protocol_version, int(kind), 0,
                             session, epoch_tag, command_id)
        body = header + payload
        return cobs_encode(body + CRC.pack(crc16_ccitt_false(body))) + b"\x00"

    def encode_hello(self, *, session_id: str | uuid.UUID, host_nonce64: int) -> bytes:
        _uint(host_nonce64, 64, "host_nonce64", nonzero=True)
        return self.encode_message(MessageType.HELLO, session_id=session_id,
                                   epoch_tag=0, command_id=0, payload=struct.pack("<Q", host_nonce64))

    def encode_arm(self, *, session_id: str | uuid.UUID, epoch_tag: int,
                   command_id: int, stage_context_token: int,
                   direction: int = DriveDirection.FWD) -> bytes:
        _uint(stage_context_token, 16, "stage_context_token", nonzero=True)
        _uint(int(direction), 8, "direction")
        if int(direction) not in {int(DriveDirection.FWD), int(DriveDirection.REV)}:
            raise ProtocolV2Error("direction must be FWD(0) or REV(1)")
        return self.encode_message(MessageType.ARM, session_id=session_id, epoch_tag=epoch_tag,
                                   command_id=command_id,
                                   payload=struct.pack("<HBB", stage_context_token, 0, int(direction)))

    def encode_disarm(self, *, session_id: str | uuid.UUID, epoch_tag: int,
                      command_id: int, stage_context_token: int) -> bytes:
        _uint(stage_context_token, 16, "stage_context_token", nonzero=True)
        return self.encode_message(MessageType.DISARM, session_id=session_id, epoch_tag=epoch_tag,
                                   command_id=command_id, payload=struct.pack("<H", stage_context_token))

    def encode_pwm_set(self, *, session_id: str | uuid.UUID, epoch_tag: int,
                       command_id: int, pwm: int, stage_context_token: int) -> bytes:
        if isinstance(pwm, bool) or not isinstance(pwm, int) or not 0 <= pwm <= 30:
            raise ProtocolV2Error("PWM must be integer 0..30")
        _uint(stage_context_token, 16, "stage_context_token", nonzero=True)
        return self.encode_message(MessageType.PWM_SET, session_id=session_id,
                                   epoch_tag=epoch_tag, command_id=command_id,
                                   payload=struct.pack("<BH", pwm, stage_context_token))

    def encode_stop_request(self, *, session_id: str | uuid.UUID | bytes,
                            epoch_tag: int, command_id: int, stop_reason: int,
                            stop_request_id: int) -> bytes:
        _uint(stop_request_id, 16, "stop_request_id", nonzero=True)
        _uint(stop_reason, 8, "stop_reason")
        if stop_reason not in {int(reason) for reason in StopReason}:
            raise ProtocolV2Error("stop_reason must use an assigned StopReason code")
        return self.encode_message(MessageType.STOP_REQ, session_id=session_id,
                                   epoch_tag=epoch_tag, command_id=command_id,
                                   payload=struct.pack("<BH", stop_reason, stop_request_id))

    def decode(self, payload: bytes) -> DecodedFrame:
        if not isinstance(payload, (bytes, bytearray, memoryview)):
            raise ProtocolV2Error("stream input must be bytes-like")
        raw = bytes(payload)
        delimiter = raw.find(b"\x00")
        if delimiter < 0:
            raise IncompleteMessage()
        if delimiter == 0:
            raise ProtocolV2Error("empty COBS frame")
        decoded = cobs_decode(raw[:delimiter])
        if len(decoded) < HEADER_SIZE + CRC_SIZE:
            raise ProtocolV2Error("decoded frame shorter than header and CRC")
        body, crc_bytes = decoded[:-CRC_SIZE], decoded[-CRC_SIZE:]
        expected_crc, = CRC.unpack(crc_bytes)
        if crc16_ccitt_false(body) != expected_crc:
            raise ProtocolV2Error("CRC-16/CCITT-FALSE mismatch")
        magic, version, kind_value, flags, session, epoch_tag, command_id = HEADER.unpack(body[:HEADER_SIZE])
        if magic != self.magic or version != self.protocol_version:
            raise ProtocolV2Error("magic or protocol_version mismatch")
        if flags != 0:
            raise ProtocolV2Error("reserved header flags must be zero")
        try:
            kind = MessageType(kind_value)
        except ValueError as exc:
            raise ProtocolV2Error("unknown message_type") from exc
        self._validate_header(kind, session, epoch_tag, command_id)
        if len(body) != HEADER_SIZE + _PAYLOAD_LENGTHS[kind]:
            raise ProtocolV2Error(f"{kind.name} decoded length mismatch")
        p = body[HEADER_SIZE:]
        self._validate_payload(kind, p)
        message = self._decode_payload(kind, p)
        if kind == MessageType.HELLO_ACK and message["boot_id64"]:
            if epoch_tag_for_boot_id(message["boot_id64"]) != epoch_tag:
                raise ProtocolV2Error("HELLO_ACK epoch tag does not match full boot_id64")
        message.update({
            "kind": kind.name, "message_type": int(kind),
            "measurement_session_id": _uuid_text(session),
            "device_epoch_tag": epoch_tag, "command_id": command_id,
            "magic": magic, "protocol_version": version,
        })
        return DecodedFrame(message=message, consumed_bytes=delimiter + 1)

    def _validate_payload(self, kind: MessageType, p: bytes) -> None:
        if kind == MessageType.HELLO:
            nonce, = struct.unpack("<Q", p)
            _uint(nonce, 64, "host_nonce64", nonzero=True)
        elif kind == MessageType.HELLO_ACK:
            result, boot, nonce, _next = struct.unpack("<BQQQ", p)
            if result not in _HELLO_RESULTS or nonce == 0:
                raise ProtocolV2Error("invalid HELLO_ACK result/nonce")
            if result == 0 and boot == 0:
                raise ProtocolV2Error("successful HELLO_ACK requires nonzero boot_id64")
            if result == 1 and boot != 0:
                raise ProtocolV2Error("BOOT_ID_INVALID HELLO_ACK must return boot_id64=0")
        elif kind == MessageType.ARM:
            token, initial_pwm, direction = struct.unpack("<HBB", p)
            if token == 0 or initial_pwm != 0 or direction not in {0, 1}:
                raise ProtocolV2Error("ARM requires nonzero token, initial_pwm=0 and FWD/REV direction")
        elif kind == MessageType.ARM_ACK:
            result, state, token, direction = struct.unpack("<BBHB", p)
            if result not in _ARM_RESULTS or state not in _STATE_NAMES or direction not in {0, 1, 0xFF}:
                raise ProtocolV2Error("invalid ARM_ACK fields")
            if result == 0 and (state != 1 or token == 0 or direction not in {0, 1}):
                raise ProtocolV2Error("successful ARM_ACK must report ARMED and echo token/direction")
        elif kind == MessageType.DISARM:
            token, = struct.unpack("<H", p)
            if token == 0:
                raise ProtocolV2Error("DISARM requires a nonzero active context token")
        elif kind == MessageType.DISARM_ACK:
            result, state, token = struct.unpack("<BBH", p)
            if result not in {0, 1, 2} or state not in _STATE_NAMES or token == 0:
                raise ProtocolV2Error("invalid DISARM_ACK fields")
            if result == 0 and state != 0:
                raise ProtocolV2Error("successful DISARM_ACK must report IDLE")
        elif kind == MessageType.PWM_SET:
            pwm, token = struct.unpack("<BH", p)
            if pwm > 30 or token == 0:
                raise ProtocolV2Error("invalid PWM_SET PWM/context")
        elif kind == MessageType.APPLY_ACK:
            result, applied_pwm, token = struct.unpack("<BBH", p)
            if result not in _APPLY_RESULTS or applied_pwm > 30 or token == 0:
                raise ProtocolV2Error("invalid APPLY_ACK fields")
            if result != 0 and applied_pwm != 0:
                raise ProtocolV2Error("rejected APPLY_ACK must echo applied_pwm=0")
        elif kind == MessageType.STOP_REQ:
            reason, request_id = struct.unpack("<BH", p)
            if request_id == 0 or reason == 0:
                raise ProtocolV2Error("STOP_REQ requires nonzero reason and request ID")
        elif kind == MessageType.STOP_ACK:
            relation, outcome, state = struct.unpack("<BBB", p)
            if relation not in _STOP_RELATIONS or outcome not in _STOP_OUTCOMES or state not in _STOP_STATES:
                raise ProtocolV2Error("invalid STOP_ACK enum")
        elif kind == MessageType.STATUS:
            state, pwm, token, _loss, _next = struct.unpack("<BBHIQ", p)
            if state not in _STATE_NAMES or pwm > 30:
                raise ProtocolV2Error("invalid STATUS state/PWM")
        elif kind == MessageType.ERROR:
            error, _offending, _detail, _related = struct.unpack("<BBHI", p)
            if error not in _ERROR_CODES:
                raise ProtocolV2Error("invalid ERROR code")
        elif kind == MessageType.ADC_BATCH:
            first, flags, count, _loss = struct.unpack("<QBBB", p[:11])
            if count != 12:
                raise ProtocolV2Error("ADC_BATCH requires exactly 12 sample slots")
            if first > 0xFFFFFFFFFFFFFFFF - count:
                raise ProtocolV2Error("ADC_BATCH sample sequence overflows uint64")
            if flags != 0:
                raise ProtocolV2Error("reserved ADC_BATCH flags must be zero")
            for offset in range(11, len(p), ADC_SAMPLE_SIZE):
                _timestamp, channel, adc_raw, _token, status, sample_flags = struct.unpack(
                    "<IBHHBH", p[offset:offset + ADC_SAMPLE_SIZE]
                )
                if channel > 5 or status > 3 or sample_flags != 0:
                    raise ProtocolV2Error("invalid ADC sample channel/status/flags")
                if (status == 0 and adc_raw > 1023) or (status != 0 and adc_raw != 0xFFFF):
                    raise ProtocolV2Error("ADC raw/status combination violates v2")
        else:
            raise ProtocolV2Error("unsupported message type")

    def _decode_payload(self, kind: MessageType, p: bytes) -> dict[str, Any]:
        if kind == MessageType.HELLO:
            nonce, = struct.unpack("<Q", p)
            return {"host_nonce64": nonce}
        if kind == MessageType.HELLO_ACK:
            result, boot, nonce, next_sequence = struct.unpack("<BQQQ", p)
            return {"result": result, "boot_id64": boot,
                    "echoed_host_nonce64": nonce, "next_sample_sequence64": next_sequence}
        if kind == MessageType.ARM:
            token, pwm, direction = struct.unpack("<HBB", p)
            return {"stage_context_token": token, "initial_pwm": pwm,
                    "direction": "FWD" if direction == 0 else "REV", "direction_code": direction}
        if kind == MessageType.ARM_ACK:
            result, state, token, direction = struct.unpack("<BBHB", p)
            return {"result": result, "state": _STATE_NAMES[state], "state_code": state,
                    "active_context_token": token,
                    "direction": {0: "FWD", 1: "REV", 0xFF: "NONE"}[direction],
                    "direction_code": direction}
        if kind == MessageType.DISARM:
            token, = struct.unpack("<H", p)
            return {"stage_context_token": token}
        if kind == MessageType.DISARM_ACK:
            result, state, token = struct.unpack("<BBH", p)
            return {"result": result, "state": _STATE_NAMES[state], "state_code": state,
                    "stage_context_token": token}
        if kind == MessageType.PWM_SET:
            pwm, token = struct.unpack("<BH", p)
            return {"pwm": pwm, "stage_context_token": token}
        if kind == MessageType.APPLY_ACK:
            result, pwm, token = struct.unpack("<BBH", p)
            return {"result": result, "applied_pwm": pwm, "stage_context_token": token}
        if kind == MessageType.STOP_REQ:
            reason, request_id = struct.unpack("<BH", p)
            return {"stop_reason": reason, "stop_request_id": request_id}
        if kind == MessageType.STOP_ACK:
            relation, outcome, state = struct.unpack("<BBB", p)
            return {"requester_relation": relation, "request_outcome": outcome, "latched_state": state}
        if kind == MessageType.STATUS:
            state, pwm, token, loss, next_sequence = struct.unpack("<BBHIQ", p)
            return {"state": _STATE_NAMES[state], "state_code": state,
                    "active_pwm": pwm, "active_context_token": token,
                    "loss_counter": loss, "next_sample_sequence64": next_sequence}
        if kind == MessageType.ERROR:
            error, offending, detail, related = struct.unpack("<BBHI", p)
            return {"error_code": error, "offending_message_type": offending,
                    "detail_code": detail, "related_command_id": related}
        if kind == MessageType.ADC_BATCH:
            first, batch_flags, count, loss = struct.unpack("<QBBB", p[:11])
            samples = []
            for index, offset in enumerate(range(11, len(p), ADC_SAMPLE_SIZE)):
                timestamp, channel, adc_raw, token, status, sample_flags = struct.unpack(
                    "<IBHHBH", p[offset:offset + ADC_SAMPLE_SIZE]
                )
                samples.append({
                    "sample_sequence64": first + index,
                    "timestamp_us_u32": timestamp,
                    "channel_code": channel, "adc_raw": adc_raw,
                    "stage_context_token": token, "acquisition_status": status,
                    "sample_flags": sample_flags,
                })
            return {"first_sample_sequence64": first, "batch_flags": batch_flags,
                    "sample_count": count, "loss_counter_snapshot": loss,
                    "samples": samples, "raw_payload": p}
        raise ProtocolV2Error("unsupported message type")
