import struct
import uuid

import pytest

from measurement_310.command_intent import DurableIntentJournal
from measurement_310.protocol_v1_session import TransportEvidenceJournal
from measurement_310.protocol_v2 import (
    MessageType, ProtocolV2Codec, PROTOCOL_V2_MAGIC, PROTOCOL_V2_VERSION,
    DriveDirection, epoch_tag_for_boot_id,
)
from measurement_310.protocol_v2_session import ProtocolV2HostSession, ProtocolV2SessionError
from measurement_310.device_loss_accounting import DeviceLossWindowAccumulator


BOOT = 0x123456789ABCDEF0
CODEC = ProtocolV2Codec(PROTOCOL_V2_MAGIC, PROTOCOL_V2_VERSION)


class ScriptedTransport:
    def __init__(self, session_id, next_sequence=0):
        self.session_id = session_id
        self.next_sequence = next_sequence
        self.connected = False
        self.incoming = []
        self.sent = []

    def connect(self):
        self.connected = True

    def disconnect(self):
        self.connected = False

    def send(self, payload):
        self.sent.append(bytes(payload))
        request = CODEC.decode(payload).message
        kind = request["kind"]
        session = request["measurement_session_id"]
        epoch = epoch_tag_for_boot_id(BOOT)
        if kind == "HELLO":
            response = CODEC.encode_message(
                MessageType.HELLO_ACK, session_id=session, epoch_tag=epoch,
                payload=struct.pack("<BQQQ", 0, BOOT, request["host_nonce64"], self.next_sequence),
            )
            self.incoming.append(response)
        elif kind == "ARM":
            token = request["stage_context_token"]
            self.incoming.append(CODEC.encode_message(
                MessageType.ARM_ACK, session_id=session, epoch_tag=epoch,
                command_id=request["command_id"], payload=struct.pack("<BBHB", 0, 1, token, request["direction_code"]),
            ))
        elif kind == "DISARM":
            token = request["stage_context_token"]
            self.incoming.append(CODEC.encode_message(
                MessageType.DISARM_ACK, session_id=session, epoch_tag=epoch,
                command_id=request["command_id"], payload=struct.pack("<BBH", 0, 0, token),
            ))
        elif kind == "PWM_SET":
            token = request["stage_context_token"]
            self.incoming.append(CODEC.encode_message(
                MessageType.APPLY_ACK, session_id=session, epoch_tag=epoch,
                command_id=request["command_id"],
                payload=struct.pack("<BBH", 0, request["pwm"], token),
            ))

    def receive(self, timeout_s):
        return self.incoming.pop(0) if self.incoming else None


def make_session(tmp_path, transport, stop_writer=None):
    return ProtocolV2HostSession(
        transport, CODEC,
        DurableIntentJournal(tmp_path / "intent.jsonl"),
        TransportEvidenceJournal(tmp_path / "transport-evidence.jsonl"),
        stop_writer=stop_writer,
    )


def test_v2_host_session_uses_full_uuid_and_device_sequence(tmp_path):
    session_id = str(uuid.uuid4())
    transport = ScriptedTransport(session_id, next_sequence=1234)
    session = make_session(tmp_path, transport)
    session.start_session(session_id)
    assert session.measurement_session_id == session_id
    assert session.boot_id64 == BOOT
    assert session.next_sample_sequence64 == 1234
    assert session.sequence_reconciliation.gap_start_sequence64 == 0
    assert session.sequence_reconciliation.gap_end_sequence64_exclusive == 1234


def test_v2_session_stage_requires_exact_arm_and_apply_ack(tmp_path):
    session_id = str(uuid.uuid4())
    transport = ScriptedTransport(session_id)
    session = make_session(tmp_path, transport)
    sent_utc = session.send_stage_pwm(10, str(uuid.uuid4()), session_id, stage_index=0)
    ack = session.poll_apply_ack(0.0)
    assert ack is not None and ack[0] == 10
    assert ack[1] >= sent_utc
    session.disarm_stage()
    sent_utc_2 = session.send_stage_pwm(
        12, str(uuid.uuid4()), session_id, stage_index=1, direction=DriveDirection.REV
    )
    ack2 = session.poll_apply_ack(0.0)
    assert ack2 is not None and ack2[0] == 12 and ack2[1] >= sent_utc_2
    session.disarm_stage()
    messages = [CODEC.decode(x).message for x in transport.sent]
    assert [m["kind"] for m in messages] == [
        "HELLO", "ARM", "PWM_SET", "DISARM", "ARM", "PWM_SET", "DISARM"
    ]
    assert messages[1]["direction"] == "FWD"
    assert messages[4]["direction"] == "REV"
    assert session._failed is False


def test_v2_host_sequence_rollback_blocks_before_arm(tmp_path):
    session_id = str(uuid.uuid4())
    transport = ScriptedTransport(session_id, next_sequence=90)
    session = make_session(tmp_path, transport)
    with pytest.raises(ProtocolV2SessionError, match="reconciliation"):
        session.start_session(session_id, host_boot_id64=BOOT, host_next_sequence64=100)
    assert [CODEC.decode(x).message["kind"] for x in transport.sent] == ["HELLO"]


def test_v2_adc_batch_advances_full_width_sequence_and_rejects_replay(tmp_path):
    session_id = str(uuid.uuid4())
    transport = ScriptedTransport(session_id, next_sequence=0)
    session = make_session(tmp_path, transport)
    session.start_session(session_id)
    session._active_stage = {"token": 1, "stage_context_id": "stage-1"}
    session._loss_accumulator = DeviceLossWindowAccumulator(BOOT, 1)
    payload = bytearray(struct.pack("<QBBB", 0, 0, 12, 0))
    channel_order = (0, 1, 4, 5, 2, 3)
    timestamps = (0, 100, 200, 300, 400, 500, 25000, 25100, 25200, 25300, 25400, 25500)
    for i in range(12):
        payload.extend(struct.pack("<IBHHBH", timestamps[i], channel_order[i % 6], 512, 1, 0, 0))
    batch = CODEC.decode(CODEC.encode_message(
        MessageType.ADC_BATCH, session_id=session_id,
        epoch_tag=epoch_tag_for_boot_id(BOOT), payload=bytes(payload),
    )).message
    accepted = session.accept_adc_batch(batch)
    assert accepted[-1]["sample_sequence64"] == 11
    assert session.next_sample_sequence64 == 12
    with pytest.raises(ProtocolV2SessionError, match="stale or duplicate"):
        session.accept_adc_batch(batch)


def test_v2_stop_can_be_sent_without_established_session(tmp_path):
    session_id = str(uuid.uuid4())
    sent = []
    session = make_session(tmp_path, ScriptedTransport(session_id), stop_writer=sent.append)
    assert session.send_stop_best_effort(stop_reason=1, stop_request_id=1) == 1
    message = CODEC.decode(sent[0]).message
    assert message["kind"] == "STOP_REQ"
    assert message["measurement_session_id"] == "00000000-0000-0000-0000-000000000000"


@pytest.mark.parametrize("value", ["", "not-a-uuid", "00000000-0000-0000-0000-000000000000"])
def test_v2_session_rejects_invalid_measurement_session_id(tmp_path, value):
    session = make_session(tmp_path, ScriptedTransport(value))
    with pytest.raises(ValueError):
        session.start_session(value)


def test_for_rawlog_session_binds_intent_and_evidence_to_same_uuid(tmp_path):
    session_id = str(uuid.uuid4())
    transport = ScriptedTransport(session_id)
    session = ProtocolV2HostSession.for_rawlog_session(
        transport, CODEC, tmp_path, session_id,
    )
    assert session.intent_journal.path == (
        tmp_path / ".command-intents" / session_id / "command-intents-v1.jsonl"
    )
    assert session.evidence.path == (
        tmp_path / ".transport-evidence" / session_id / "transport-evidence-v1.jsonl"
    )
    with pytest.raises(ProtocolV2SessionError, match="does not match"):
        session.start_session(str(uuid.uuid4()))
    assert transport.connected is False
    session.start_session(session_id)
    assert session.measurement_session_id == session_id
    assert transport.connected is True
