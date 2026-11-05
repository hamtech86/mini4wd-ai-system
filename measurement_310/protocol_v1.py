"""310-4 v0.5 wire codec primitives.

The command authority assigns the normative v1 magic/version constants below.
Callers MUST pass them explicitly; there are intentionally no constructor defaults.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
import struct
from typing import Any

from .transport import DecodedFrame, IncompleteMessage


class ProtocolV1Error(ValueError):
    pass


class MessageType(IntEnum):
    HELLO = 0x01
    HELLO_ACK = 0x02
    ARM = 0x03
    ARM_ACK = 0x04
    PWM_SET = 0x10
    APPLY_ACK = 0x11
    STOP_REQ = 0x20
    STOP_ACK = 0x21
    STATUS = 0x30
    ERROR = 0x31
    ADC_BATCH = 0x40

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


PROTOCOL_V1_MAGIC = 0x344D
PROTOCOL_V1_VERSION = 0x01

HEADER = struct.Struct("<HBBBIII")
CRC = struct.Struct("<H")
HEADER_SIZE = 17
CRC_SIZE = 2
ADC_SAMPLE_SIZE = 14
ADC_BATCH_SIZE = 173

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
_PAYLOAD_LENGTHS = {
    MessageType.HELLO: 8,
    MessageType.HELLO_ACK: 17,
    MessageType.ARM: 3,
    MessageType.ARM_ACK: 4,
    MessageType.PWM_SET: 3,
    MessageType.APPLY_ACK: 4,
    MessageType.STOP_REQ: 3,
    MessageType.STOP_ACK: 3,
    MessageType.STATUS: 10,
    MessageType.ERROR: 8,
    MessageType.ADC_BATCH: ADC_BATCH_SIZE,
}


def crc16_ccitt_false(data: bytes) -> int:
    """CRC-16/CCITT-FALSE: init=FFFF, poly=1021, xorout=0000."""
    crc = 0xFFFF
    for octet in data:
        crc ^= octet << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def cobs_encode(data: bytes) -> bytes:
    out = bytearray([0])
    code_index = 0
    code = 1
    for octet in data:
        if octet == 0:
            out[code_index] = code
            code_index = len(out)
            out.append(0)
            code = 1
        else:
            out.append(octet)
            code += 1
            if code == 0xFF:
                out[code_index] = code
                code_index = len(out)
                out.append(0)
                code = 1
    out[code_index] = code
    return bytes(out)


def cobs_decode(data: bytes) -> bytes:
    if not data or 0 in data:
        raise ProtocolV1Error("COBS frame must be non-empty and contain no delimiter")
    out = bytearray()
    index = 0
    while index < len(data):
        code = data[index]
        if code == 0:
            raise ProtocolV1Error("zero COBS code")
        index += 1
        end = index + code - 1
        if end > len(data):
            raise ProtocolV1Error("COBS code exceeds frame boundary")
        out.extend(data[index:end])
        index = end
        if code != 0xFF and index < len(data):
            out.append(0)
    return bytes(out)


def epoch_tag_for_boot_id(boot_id64: int) -> int:
    if isinstance(boot_id64, bool) or not isinstance(boot_id64, int) or not 0 < boot_id64 <= 0xFFFFFFFFFFFFFFFF:
        raise ProtocolV1Error("boot_id64 must be a nonzero uint64")
    tag = boot_id64 & 0xFFFFFFFF
    return tag if tag else 0xFFFFFFFF


@dataclass(frozen=True)
class ProtocolV1Codec:
    """Strict v1 stream codec using the command-authority assigned wire constants."""

    magic: int
    protocol_version: int

    def __post_init__(self):
        if isinstance(self.magic, bool) or not isinstance(self.magic, int) or not 0 <= self.magic <= 0xFFFF:
            raise ValueError("magic must be explicitly supplied as uint16")
        if (isinstance(self.protocol_version, bool) or not isinstance(self.protocol_version, int)
                or not 0 <= self.protocol_version <= 0xFF):
            raise ValueError("protocol_version must be explicitly supplied as uint8")
        if self.magic != PROTOCOL_V1_MAGIC:
            raise ValueError(f"magic must equal normative v1 value 0x{PROTOCOL_V1_MAGIC:04X}")
        if self.protocol_version != PROTOCOL_V1_VERSION:
            raise ValueError(f"protocol_version must equal normative v1 value 0x{PROTOCOL_V1_VERSION:02X}")

    def _validate_header(self, message_type: MessageType, session_tag: int,
                         epoch_tag: int, command_id: int) -> None:
        for name, value, maximum in (
            ("measurement_session_tag", session_tag, 0xFFFFFFFF),
            ("device_epoch_tag", epoch_tag, 0xFFFFFFFF),
            ("command_id", command_id, 0xFFFFFFFF),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
                raise ProtocolV1Error(f"{name} must be uint32")
        if message_type in {MessageType.HELLO, MessageType.HELLO_ACK, MessageType.ARM,
                            MessageType.ARM_ACK, MessageType.PWM_SET, MessageType.APPLY_ACK,
                            MessageType.ADC_BATCH} and session_tag == 0:
            raise ProtocolV1Error("message type requires nonzero measurement_session_tag")
        if message_type in _ZERO_COMMAND_TYPES:
            if command_id != 0:
                raise ProtocolV1Error("message type requires command_id=0")
        elif command_id == 0:
            raise ProtocolV1Error("command-bearing message requires nonzero command_id")
        if message_type == MessageType.HELLO and epoch_tag != 0:
            raise ProtocolV1Error("HELLO requires device_epoch_tag=0")
        if message_type not in {MessageType.HELLO, MessageType.HELLO_ACK, MessageType.STOP_REQ,
                                MessageType.STOP_ACK, MessageType.STATUS, MessageType.ERROR} and epoch_tag == 0:
            raise ProtocolV1Error("message requires a verified nonzero epoch correlation tag")

    def encode_message(self, message_type: MessageType | int, *, session_tag: int,
                       epoch_tag: int, command_id: int = 0, payload: bytes = b"") -> bytes:
        try:
            kind = MessageType(message_type)
        except ValueError as exc:
            raise ProtocolV1Error("unsupported message type") from exc
        self._validate_header(kind, session_tag, epoch_tag, command_id)
        if not isinstance(payload, bytes) or len(payload) != _PAYLOAD_LENGTHS[kind]:
            raise ProtocolV1Error(f"{kind.name} payload must be exactly {_PAYLOAD_LENGTHS[kind]} bytes")
        self._validate_payload(kind, payload)
        header = HEADER.pack(self.magic, self.protocol_version, int(kind), 0,
                             session_tag, epoch_tag, command_id)
        body = header + payload
        decoded = body + CRC.pack(crc16_ccitt_false(body))
        return cobs_encode(decoded) + b"\x00"

    def encode_hello(self, *, session_tag: int, host_nonce64: int) -> bytes:
        self._uint(host_nonce64, 64, "host_nonce64", nonzero=True)
        return self.encode_message(MessageType.HELLO, session_tag=session_tag,
                                   epoch_tag=0, command_id=0, payload=struct.pack("<Q", host_nonce64))

    def encode_arm(self, *, session_tag: int, epoch_tag: int, command_id: int,
                   stage_context_token: int) -> bytes:
        self._uint(stage_context_token, 16, "stage_context_token", nonzero=True)
        return self.encode_message(MessageType.ARM, session_tag=session_tag, epoch_tag=epoch_tag,
                                   command_id=command_id, payload=struct.pack("<HB", stage_context_token, 0))

    def encode_pwm_set(self, *, session_tag: int, epoch_tag: int, command_id: int,
                       pwm: int, stage_context_token: int) -> bytes:
        if isinstance(pwm, bool) or not isinstance(pwm, int) or not 0 <= pwm <= 30:
            raise ProtocolV1Error("PWM must be integer 0..30")
        self._uint(stage_context_token, 16, "stage_context_token", nonzero=True)
        return self.encode_message(MessageType.PWM_SET, session_tag=session_tag,
                                   epoch_tag=epoch_tag, command_id=command_id,
                                   payload=struct.pack("<BH", pwm, stage_context_token))

    def encode_stop_request(self, *, session_tag: int, epoch_tag: int, command_id: int,
                            stop_reason: int, stop_request_id: int) -> bytes:
        self._uint(stop_request_id, 16, "stop_request_id", nonzero=True)
        self._uint(stop_reason, 8, "stop_reason")
        if stop_reason not in {int(reason) for reason in StopReason}:
            raise ProtocolV1Error("stop_reason must use an assigned StopReason code")
        return self.encode_message(MessageType.STOP_REQ, session_tag=session_tag,
                                   epoch_tag=epoch_tag, command_id=command_id,
                                   payload=struct.pack("<BH", stop_reason, stop_request_id))

    @staticmethod
    def _uint(value: int, bits: int, name: str, nonzero: bool = False) -> None:
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < (1 << bits):
            raise ProtocolV1Error(f"{name} must be uint{bits}")
        if nonzero and value == 0:
            raise ProtocolV1Error(f"{name} must be nonzero")

    def decode(self, payload: bytes) -> DecodedFrame:
        """Decode exactly the first delimiter-terminated frame in a stream buffer."""
        if not isinstance(payload, (bytes, bytearray, memoryview)):
            raise ProtocolV1Error("stream input must be bytes-like")
        raw = bytes(payload)
        delimiter = raw.find(b"\x00")
        if delimiter < 0:
            raise IncompleteMessage()
        if delimiter == 0:
            raise ProtocolV1Error("empty COBS frame")
        encoded = raw[:delimiter]
        decoded = cobs_decode(encoded)
        if len(decoded) < HEADER_SIZE + CRC_SIZE:
            raise ProtocolV1Error("decoded frame shorter than header and CRC")
        body, crc_bytes = decoded[:-CRC_SIZE], decoded[-CRC_SIZE:]
        expected_crc, = CRC.unpack(crc_bytes)
        if crc16_ccitt_false(body) != expected_crc:
            raise ProtocolV1Error("CRC-16/CCITT-FALSE mismatch")
        magic, version, kind_value, flags, session_tag, epoch_tag, command_id = HEADER.unpack(body[:HEADER_SIZE])
        if magic != self.magic or version != self.protocol_version:
            raise ProtocolV1Error("magic or protocol_version mismatch")
        if flags != 0:
            raise ProtocolV1Error("reserved header flags must be zero")
        try:
            kind = MessageType(kind_value)
        except ValueError as exc:
            raise ProtocolV1Error("unknown message_type") from exc
        self._validate_header(kind, session_tag, epoch_tag, command_id)
        expected_length = HEADER_SIZE + _PAYLOAD_LENGTHS[kind]
        if len(body) != expected_length:
            raise ProtocolV1Error(f"{kind.name} decoded length mismatch")
        message = self._decode_payload(kind, body[HEADER_SIZE:])
        if kind == MessageType.HELLO_ACK:
            if message["boot_id64"] != 0:
                if epoch_tag_for_boot_id(message["boot_id64"]) != epoch_tag:
                    raise ProtocolV1Error("HELLO_ACK epoch tag does not match full boot_id64")
            elif epoch_tag != 0:
                raise ProtocolV1Error("HELLO_ACK without valid boot identity requires epoch_tag=0")
        message.update({
            "kind": kind.name, "message_type": int(kind),
            "measurement_session_tag": session_tag,
            "device_epoch_tag": epoch_tag, "command_id": command_id,
            "magic": magic, "protocol_version": version,
        })
        return DecodedFrame(message=message, consumed_bytes=delimiter + 1)

    def _validate_payload(self, kind: MessageType, p: bytes) -> None:
        if kind == MessageType.HELLO:
            nonce, = struct.unpack("<Q", p)
            self._uint(nonce, 64, "host_nonce64", nonzero=True)
        elif kind == MessageType.HELLO_ACK:
            result, boot, nonce = struct.unpack("<BQQ", p)
            if result not in _HELLO_RESULTS or nonce == 0:
                raise ProtocolV1Error("invalid HELLO_ACK result/nonce")
            if result == 0 and boot == 0:
                raise ProtocolV1Error("successful HELLO_ACK requires nonzero boot_id64")
        elif kind == MessageType.ARM:
            token, initial_pwm = struct.unpack("<HB", p)
            if token == 0 or initial_pwm != 0:
                raise ProtocolV1Error("ARM requires nonzero context token and initial_pwm=0")
        elif kind == MessageType.ARM_ACK:
            result, state, token = struct.unpack("<BBH", p)
            if result not in _ARM_RESULTS or state not in _STATE_NAMES:
                raise ProtocolV1Error("invalid ARM_ACK fields")
            if result == 0 and (state != 1 or token == 0):
                raise ProtocolV1Error("successful ARM_ACK must report ARMED and echo token")
        elif kind == MessageType.PWM_SET:
            pwm, token = struct.unpack("<BH", p)
            if pwm > 30 or token == 0:
                raise ProtocolV1Error("invalid PWM_SET PWM/context")
        elif kind == MessageType.APPLY_ACK:
            result, applied_pwm, token = struct.unpack("<BBH", p)
            if result not in _APPLY_RESULTS or applied_pwm > 30 or token == 0:
                raise ProtocolV1Error("invalid APPLY_ACK fields")
            if result != 0 and applied_pwm != 0:
                raise ProtocolV1Error("rejected APPLY_ACK must echo applied_pwm=0")
        elif kind == MessageType.STOP_REQ:
            _, request_id = struct.unpack("<BH", p)
            if request_id == 0:
                raise ProtocolV1Error("stop_request_id must be nonzero")
        elif kind == MessageType.STOP_ACK:
            relation, outcome, state = struct.unpack("<BBB", p)
            if relation not in _STOP_RELATIONS or outcome not in _STOP_OUTCOMES or state not in _STOP_STATES:
                raise ProtocolV1Error("invalid STOP_ACK enum")
        elif kind == MessageType.STATUS:
            state, pwm, token, _, _ = struct.unpack("<BBHIH", p)
            if state not in _STATE_NAMES or pwm > 30:
                raise ProtocolV1Error("invalid STATUS state/PWM")
        elif kind == MessageType.ERROR:
            error, _, detail, _ = struct.unpack("<BBHI", p)
            if error not in _ERROR_CODES:
                raise ProtocolV1Error("invalid ERROR code")
        elif kind == MessageType.ADC_BATCH:
            batch_seq, flags, count, loss_snapshot = struct.unpack("<HBBB", p[:5])
            if count != 12:
                raise ProtocolV1Error("ADC_BATCH requires exactly 12 samples")
            for offset in range(5, len(p), ADC_SAMPLE_SIZE):
                sequence, timestamp, channel, adc_raw, token, status, sample_flags = struct.unpack(
                    "<HIBHHBH", p[offset:offset + ADC_SAMPLE_SIZE]
                )
                if channel > 5 or status > 3 or sample_flags != 0:
                    raise ProtocolV1Error("invalid ADC sample channel/status/flags")
                if (status == 0 and adc_raw > 1023) or (status != 0 and adc_raw != 0xFFFF):
                    raise ProtocolV1Error("ADC raw/status combination violates v0.5")
        else:
            raise ProtocolV1Error("unsupported message type")

    def _decode_payload(self, kind: MessageType, p: bytes) -> dict[str, Any]:
        if kind == MessageType.HELLO:
            nonce, = struct.unpack("<Q", p)
            return {"host_nonce64": nonce}
        if kind == MessageType.HELLO_ACK:
            result, boot, nonce = struct.unpack("<BQQ", p)
            if result == 0 and epoch_tag_for_boot_id(boot) == 0:
                raise ProtocolV1Error("invalid boot epoch tag")
            return {"result": result, "boot_id64": boot, "echoed_host_nonce64": nonce}
        if kind == MessageType.ARM:
            token, pwm = struct.unpack("<HB", p)
            return {"stage_context_token": token, "initial_pwm": pwm}
        if kind == MessageType.ARM_ACK:
            result, state, token = struct.unpack("<BBH", p)
            return {"result": result, "state": _STATE_NAMES[state], "state_code": state,
                    "active_context_token": token}
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
            state, pwm, token, loss, last = struct.unpack("<BBHIH", p)
            return {"state": _STATE_NAMES[state], "state_code": state, "active_pwm": pwm,
                    "active_context_token": token, "loss_counter": loss,
                    "last_sample_sequence": last}
        if kind == MessageType.ERROR:
            error, offending, detail, related = struct.unpack("<BBHI", p)
            return {"error_code": error, "offending_message_type": offending,
                    "detail_code": detail, "related_command_id": related}
        if kind == MessageType.ADC_BATCH:
            batch_sequence, batch_flags, sample_count, loss_snapshot = struct.unpack("<HBBB", p[:5])
            samples = []
            for offset in range(5, len(p), ADC_SAMPLE_SIZE):
                sequence, timestamp, channel, adc_raw, token, status, sample_flags = struct.unpack(
                    "<HIBHHBH", p[offset:offset + ADC_SAMPLE_SIZE]
                )
                samples.append({
                    "sample_sequence": sequence, "timestamp_us_u32": timestamp,
                    "channel_code": channel, "adc_raw": adc_raw,
                    "stage_context_token": token, "acquisition_status": status,
                    "sample_flags": sample_flags,
                })
            return {"batch_sequence": batch_sequence, "batch_flags": batch_flags,
                    "sample_count": sample_count, "loss_counter_snapshot": loss_snapshot,
                    "samples": samples, "raw_payload": p}
        raise ProtocolV1Error("unsupported message type")
