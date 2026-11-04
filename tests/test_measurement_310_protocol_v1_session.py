import json
import struct
from types import SimpleNamespace

import pytest

from measurement_310.command_intent import DurableIntentJournal
from measurement_310.protocol_v1 import MessageType, ProtocolV1Codec, epoch_tag_for_boot_id
from measurement_310.protocol_v1_session import ProtocolV1HostSession, TransportEvidenceJournal
from measurement_310.transport import MockTransport


MAGIC_FIXTURE = 0x4D34
VERSION_FIXTURE = 1
BOOT_ID = 0x1122334455667788
NONCE = 0xAABBCCDDEEFF0011


class FixedAllocator:
    def __init__(self, tag=37):
        self.tag = tag
        self.calls = 0

    def allocate(self):
        self.calls += 1
        return SimpleNamespace(tag=self.tag)


def ack_frame(codec, kind, *, session=37, epoch=None, command=0, payload):
    return codec.encode_message(
        kind, session_tag=session,
        epoch_tag=epoch if epoch is not None else epoch_tag_for_boot_id(BOOT_ID),
        command_id=command, payload=payload,
    )


def make_session(tmp_path, monkeypatch, incoming):
    monkeypatch.setattr("measurement_310.protocol_v1_session.secrets.randbits",
                        lambda bits: NONCE)
    codec = ProtocolV1Codec(MAGIC_FIXTURE, VERSION_FIXTURE)
    transport = MockTransport()
    for frame in incoming:
        transport.queue(frame)
    evidence = TransportEvidenceJournal(tmp_path / "transport-evidence-v1.jsonl")
    session = ProtocolV1HostSession(
        transport, codec, FixedAllocator(),
        DurableIntentJournal(tmp_path / "command-intent.jsonl"),
        evidence, ack_timeout_s=0.2,
    )
    return session, transport, codec, evidence


def handshake_frames(codec):
    hello = ack_frame(codec, MessageType.HELLO_ACK,
                      payload=struct.pack("<BQQ", 0, BOOT_ID, NONCE))
    arm = ack_frame(codec, MessageType.ARM_ACK, command=1,
                    payload=struct.pack("<BBH", 0, 1, 1))
    return hello, arm


def test_protocol_session_durable_intent_handshake_arm_and_exact_apply_ack(tmp_path, monkeypatch):
    codec = ProtocolV1Codec(MAGIC_FIXTURE, VERSION_FIXTURE)
    hello, arm = handshake_frames(codec)
    apply = ack_frame(codec, MessageType.APPLY_ACK, command=2,
                      payload=struct.pack("<BBH", 0, 0, 1))
    session, transport, codec, evidence = make_session(tmp_path, monkeypatch, [hello, arm, apply])

    sent_at = session.send_stage_pwm(0, "00000000-0000-4000-8000-000000000001",
                                     "00000000-0000-4000-8000-000000000002", stage_index=0)
    assert sent_at.endswith("Z")
    assert session.poll_apply_ack(0.0)[0] == 0
    assert len(transport.sent) == 3
    sent_kinds = [codec.decode(frame).message["kind"] for frame in transport.sent]
    assert sent_kinds == ["HELLO", "ARM", "PWM_SET"]

    events, _ = evidence._read()
    names = [event["event"] for event in events]
    assert names.index("RX_BYTES") < names.index("HELLO_ACK_MATCHED")
    assert names.index("STAGE_CONTEXT_MAP") < names.index("FRAME_TX_INTENT", names.index("STAGE_CONTEXT_MAP"))
    assert names.count("FRAME_TX_INTENT") == 3
    assert names.count("FRAME_TX_COMPLETE") == 3
    assert names.count("ACK_MATCHED") == 2
    context_map = next(event["payload"] for event in events
                       if event["event"] == "STAGE_CONTEXT_MAP")
    assert context_map["command_id"] == 2
    assert context_map["measurement_session_tag"] == 37
    command_tx = [event for event in events if event["event"] == "FRAME_TX_INTENT"
                  and event["payload"]["kind"] in {"ARM", "PWM_SET"}]
    assert all(event["payload"]["identity"] for event in command_tx)
    assert all(event["payload"]["intent_journal_sha256"] for event in command_tx)
    assert "00000000-0000-4000-8000-000000000001" in json.dumps(events)


def test_protocol_session_does_not_send_arm_if_durable_intent_fails(tmp_path, monkeypatch):
    codec = ProtocolV1Codec(MAGIC_FIXTURE, VERSION_FIXTURE)
    hello, arm = handshake_frames(codec)
    session, transport, _, _ = make_session(tmp_path, monkeypatch, [hello, arm])

    def fail_intent(*args, **kwargs):
        raise OSError("intent fsync failed")

    session.intent_journal.append_intent = fail_intent
    with pytest.raises(OSError, match="intent fsync failed"):
        session.send_stage_pwm(0, "stage-uuid", "session-uuid", stage_index=0)
    sent_kinds = [codec.decode(frame).message["kind"] for frame in transport.sent]
    assert sent_kinds == ["HELLO"]
    assert session._failed is True


def test_protocol_session_does_not_send_pwm_if_tx_intent_evidence_fails(tmp_path, monkeypatch):
    codec = ProtocolV1Codec(MAGIC_FIXTURE, VERSION_FIXTURE)
    hello, arm = handshake_frames(codec)
    session, transport, _, evidence = make_session(tmp_path, monkeypatch, [hello, arm])
    original_append = evidence.append

    def fail_pwm_intent(event, payload):
        if event == "FRAME_TX_INTENT" and payload.get("kind") == "PWM_SET":
            raise OSError("Evidence fsync failed")
        return original_append(event, payload)

    evidence.append = fail_pwm_intent
    with pytest.raises(OSError, match="Evidence fsync failed"):
        session.send_stage_pwm(0, "stage-uuid", "session-uuid", stage_index=0)
    sent_kinds = [codec.decode(frame).message["kind"] for frame in transport.sent]
    assert sent_kinds == ["HELLO", "ARM"]
    assert session._failed is True


def test_protocol_session_rejects_wrong_command_ack_without_advancing(tmp_path, monkeypatch):
    codec = ProtocolV1Codec(MAGIC_FIXTURE, VERSION_FIXTURE)
    hello, arm = handshake_frames(codec)
    wrong = ack_frame(codec, MessageType.APPLY_ACK, command=999,
                      payload=struct.pack("<BBH", 0, 0, 1))
    right = ack_frame(codec, MessageType.APPLY_ACK, command=2,
                      payload=struct.pack("<BBH", 0, 0, 1))
    session, _, _, _ = make_session(tmp_path, monkeypatch, [hello, arm, wrong, right])
    session.send_stage_pwm(0, "stage-uuid", "session-uuid", stage_index=0)
    assert session.poll_apply_ack(0.0) is None
    assert session.poll_apply_ack(0.0)[0] == 0


def test_protocol_session_evidence_torn_tail_fails_closed(tmp_path):
    path = tmp_path / "evidence.jsonl"
    journal = TransportEvidenceJournal(path)
    journal.append("ONE", {"value": 1})
    path.write_bytes(path.read_bytes() + b'{"torn":')
    with pytest.raises(RuntimeError, match="torn final line"):
        journal.append("TWO", {"value": 2})


def test_sequence_controller_uses_protocol_session_and_does_not_call_legacy_sender(tmp_path):
    from datetime import datetime, timezone
    from measurement_310.engine import SequenceController, SequenceState
    from raw_log_v2 import RawLogV2Writer

    class Clock:
        def __init__(self):
            self.ns = 1_000_000_000

        def monotonic_ns(self):
            return self.ns

        def utc_now(self):
            return "2026-11-04T14:00:00.000Z"

    class Adapter:
        def __init__(self):
            self.calls = []
            self.acks = [(0, "2026-11-04T14:00:00.010Z", 1_020_000_000)]
            self.last_write_completed_monotonic_ns = 1_010_000_000

        def send_stage_pwm(self, pwm, stage_context_id, measurement_session_id, stage_index=None):
            self.calls.append((pwm, stage_context_id, measurement_session_id, stage_index))
            return "2026-11-04T14:00:00.000Z"

        def poll_apply_ack(self, timeout_s=0.0):
            ack = self.acks.pop(0) if self.acks else None
            if ack is not None:
                clock.ns = ack[2] + 1
            return ack

    clock = Clock()
    adapter = Adapter()
    legacy_calls = []
    fields = {
        "log_id": "PROTOCOL-SESSION-TEST",
        "measurement_session_id": "00000000-0000-4000-8000-000000000002",
        "started_at_utc": clock.utc_now(),
        "motor_instance_id": None,
        "device": {"type": None, "model": None, "firmware_version": None,
                   "firmware_build": None, "firmware_id": None, "adc_resolution_bits": None},
        "measurement_conditions": {"direction": "UNKNOWN", "voltage_control_mode": "UNKNOWN",
            "sweep_pwm_min": 0, "sweep_pwm_max": 30, "stage_duration_ms": 10000,
            "schedule_owner": "PYTHON"},
    }
    controller = SequenceController.with_protocol_session(
        RawLogV2Writer(tmp_path), fields, adapter, lambda: None, clock,
    )
    controller.startup_recover()
    controller.start()
    assert controller.state == SequenceState.WAITING_ACK
    assert adapter.calls[0][0] == 0
    assert adapter.calls[0][2] == fields["measurement_session_id"]
    assert adapter.calls[0][3] == 0
    assert legacy_calls == []
    assert controller.poll() == SequenceState.RUNNING
    assert controller.command_sent_ns == 1_010_000_000
    assert controller.stage_start_ns == 1_020_000_000


@pytest.mark.parametrize("ack_ns,now_ns,expected_fault", [
    (1_000_000_000, 1_020_000_000, "ACK receive timestamp precedes command write completion"),
    (1_020_000_000, 12_000_000_000, "durable ACK evidence/RawLog commit exceeded stage deadline"),
])
def test_sequence_controller_fails_closed_on_invalid_or_late_ack_timing(
    tmp_path, ack_ns, now_ns, expected_fault
):
    from measurement_310.engine import SequenceController, SequenceState
    from raw_log_v2 import RawLogV2Writer

    class Clock:
        ns = 1_000_000_000

        def monotonic_ns(self):
            return self.ns

        def utc_now(self):
            return "2026-11-04T14:00:00.000Z"

    class Adapter:
        last_write_completed_monotonic_ns = 1_010_000_000

        def send_stage_pwm(self, pwm, stage_context_id, measurement_session_id, stage_index=None):
            return "2026-11-04T14:00:00.000Z"

        def poll_apply_ack(self, timeout_s=0.0):
            clock.ns = now_ns
            return 0, "2026-11-04T14:00:00.010Z", ack_ns

    clock = Clock()
    stops = []
    fields = {
        "log_id": "PROTOCOL-TIMING-FAIL",
        "measurement_session_id": "00000000-0000-4000-8000-000000000003",
        "started_at_utc": clock.utc_now(),
        "motor_instance_id": None,
        "device": {"type": None, "model": None, "firmware_version": None,
                   "firmware_build": None, "firmware_id": None, "adc_resolution_bits": None},
        "measurement_conditions": {"direction": "UNKNOWN", "voltage_control_mode": "UNKNOWN",
            "sweep_pwm_min": 0, "sweep_pwm_max": 30, "stage_duration_ms": 10000,
            "schedule_owner": "PYTHON"},
    }
    controller = SequenceController(
        RawLogV2Writer(tmp_path), fields, lambda pwm: clock.utc_now(),
        lambda: stops.append("STOP"), lambda: None, clock,
        protocol_session=Adapter(),
    )
    controller.startup_recover()
    controller.start()
    assert controller.poll() == SequenceState.FAULT
    assert stops == ["STOP"]
    assert expected_fault in str(controller._last_fault)


def test_sequence_controller_requires_callbacks_or_v1_session(tmp_path):
    from measurement_310.engine import SequenceController
    from raw_log_v2 import RawLogV2Writer

    with pytest.raises(ValueError, match="legacy send_pwm and poll_ack"):
        SequenceController(
            RawLogV2Writer(tmp_path), {}, None, lambda: None, None,
        )
