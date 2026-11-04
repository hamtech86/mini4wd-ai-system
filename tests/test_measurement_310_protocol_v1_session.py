import json
import struct
from types import SimpleNamespace

import pytest

from measurement_310.command_intent import DurableIntentJournal
from measurement_310.protocol_v1 import (MessageType, ProtocolV1Codec, PROTOCOL_V1_MAGIC,
                                          PROTOCOL_V1_VERSION, StopReason, epoch_tag_for_boot_id)
from measurement_310.protocol_v1_session import ProtocolV1HostSession, TransportEvidenceJournal
from measurement_310.transport import MockTransport


MAGIC_FIXTURE = PROTOCOL_V1_MAGIC
VERSION_FIXTURE = PROTOCOL_V1_VERSION
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


def make_session(tmp_path, monkeypatch, incoming, stop_writer=None, transport=None):
    monkeypatch.setattr("measurement_310.protocol_v1_session.secrets.randbits",
                        lambda bits: NONCE)
    codec = ProtocolV1Codec(MAGIC_FIXTURE, VERSION_FIXTURE)
    transport = transport or MockTransport()
    for frame in incoming:
        transport.queue(frame)
    evidence = TransportEvidenceJournal(tmp_path / "transport-evidence-v1.jsonl")
    session = ProtocolV1HostSession(
        transport, codec, FixedAllocator(),
        DurableIntentJournal(tmp_path / "command-intent.jsonl"),
        evidence, stop_writer=stop_writer, ack_timeout_s=0.2,
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
    required_common = {
        "schema_version", "event_id", "event_type", "measurement_session_id",
        "device_epoch_id", "host_received_at_utc", "host_received_monotonic_ns",
        "host_event_at_utc", "host_event_monotonic_ns", "direction",
    }
    assert all(required_common.issubset(event) for event in events)
    assert all(event["schema_version"] == "transport-evidence-v1" for event in events)
    assert all(event["measurement_session_id"] == "00000000-0000-4000-8000-000000000002"
               for event in events)
    assert next(event for event in events if event["event"] == "ACK_MATCHED")["device_epoch_id"] == str(BOOT_ID)
    received_frames = [event for event in events if event["event_type"] == "frame_rx_received"]
    assert len(received_frames) == 3
    ack_events = [event for event in events if event["event"] == "ACK_MATCHED"]
    assert all(event["payload"]["message"]["_raw_frame_base64"] for event in ack_events)
    assert all(event["payload"]["message"]["_rx_evidence_event_id"] for event in ack_events)
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

    def fail_pwm_intent(event, payload, **kwargs):
        if event == "FRAME_TX_INTENT" and payload.get("kind") == "PWM_SET":
            raise OSError("Evidence fsync failed")
        return original_append(event, payload, **kwargs)

    evidence.append = fail_pwm_intent
    with pytest.raises(OSError, match="Evidence fsync failed"):
        session.send_stage_pwm(0, "stage-uuid", "session-uuid", stage_index=0)
    sent_kinds = [codec.decode(frame).message["kind"] for frame in transport.sent]
    assert sent_kinds == ["HELLO", "ARM"]
    assert session._failed is True


def test_protocol_session_missing_ack_keeps_command_pending_and_blocks_next_stage(
    tmp_path, monkeypatch
):
    codec = ProtocolV1Codec(MAGIC_FIXTURE, VERSION_FIXTURE)
    hello, arm = handshake_frames(codec)
    session, transport, _, _ = make_session(tmp_path, monkeypatch, [hello, arm])
    session.send_stage_pwm(0, "stage-zero", "session-uuid", stage_index=0)

    assert session.poll_apply_ack(0.0) is None
    assert session._pending is not None
    sent_before = list(transport.sent)
    with pytest.raises(RuntimeError, match="previous PWM command outcome is unresolved"):
        session.send_stage_pwm(1, "stage-one", "session-uuid", stage_index=1)
    assert session._failed is True
    assert transport.sent == sent_before


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


def test_protocol_session_stage_context_evidence_failure_suppresses_arm_and_pwm(
    tmp_path, monkeypatch
):
    codec = ProtocolV1Codec(MAGIC_FIXTURE, VERSION_FIXTURE)
    hello, arm = handshake_frames(codec)
    session, transport, _, evidence = make_session(tmp_path, monkeypatch, [hello, arm])
    original_append = evidence.append

    def fail_context_map(event, payload, **kwargs):
        if event == "STAGE_CONTEXT_MAP":
            raise OSError("injected context map durability failure")
        return original_append(event, payload, **kwargs)

    evidence.append = fail_context_map
    with pytest.raises(OSError, match="context map durability failure"):
        session.send_stage_pwm(0, "stage-uuid", "session-uuid", stage_index=0)
    assert session._failed is True
    assert [session.codec.decode(frame).message["kind"] for frame in transport.sent] == ["HELLO"]


def test_protocol_session_pwm_write_complete_evidence_failure_is_unknown(
    tmp_path, monkeypatch
):
    codec = ProtocolV1Codec(MAGIC_FIXTURE, VERSION_FIXTURE)
    hello, arm = handshake_frames(codec)
    session, transport, _, evidence = make_session(tmp_path, monkeypatch, [hello, arm])
    original_append = evidence.append

    def fail_pwm_complete(event, payload, **kwargs):
        if event == "FRAME_TX_COMPLETE" and payload.get("kind") == "PWM_SET":
            raise OSError("injected PWM completion evidence failure")
        return original_append(event, payload, **kwargs)

    evidence.append = fail_pwm_complete
    with pytest.raises(OSError, match="PWM completion evidence failure"):
        session.send_stage_pwm(0, "stage-uuid", "session-uuid", stage_index=0)
    assert session._failed is True
    assert [session.codec.decode(frame).message["kind"] for frame in transport.sent] == [
        "HELLO", "ARM", "PWM_SET"
    ]
    assert session._pending is None
    with pytest.raises(RuntimeError, match="fail-closed"):
        session.send_stage_pwm(1, "next-stage", "session-uuid", stage_index=1)


@pytest.mark.parametrize("failed_event", ["RX_BYTES", "FRAME_RX_DECODED", "ACK_MATCHED"])
def test_protocol_session_ack_evidence_failure_never_releases_stage(
    tmp_path, monkeypatch, failed_event
):
    codec = ProtocolV1Codec(MAGIC_FIXTURE, VERSION_FIXTURE)
    hello, arm = handshake_frames(codec)
    apply = ack_frame(codec, MessageType.APPLY_ACK, command=2,
                      payload=struct.pack("<BBH", 0, 0, 1))
    session, _, _, evidence = make_session(tmp_path, monkeypatch, [hello, arm, apply])
    session.send_stage_pwm(0, "stage-uuid", "session-uuid", stage_index=0)

    original_append = evidence.append

    def fail_selected_evidence(event, payload, **kwargs):
        if event == failed_event:
            raise OSError(f"injected {failed_event} durability failure")
        return original_append(event, payload, **kwargs)

    evidence.append = fail_selected_evidence
    with pytest.raises(OSError, match=f"injected {failed_event} durability failure"):
        session.poll_apply_ack(0.0)

    assert session._failed is True
    assert session._pending is not None
    with pytest.raises(RuntimeError, match="fail-closed"):
        session.send_stage_pwm(1, "next-stage", "session-uuid", stage_index=1)


@pytest.mark.parametrize("mismatch", [
    "session", "epoch", "context", "applied_pwm", "result", "message_type",
])
def test_protocol_session_rejects_wrong_ack_identity_fields_without_stage_release(
    tmp_path, monkeypatch, mismatch
):
    codec = ProtocolV1Codec(MAGIC_FIXTURE, VERSION_FIXTURE)
    hello, arm = handshake_frames(codec)
    kind = MessageType.APPLY_ACK
    session_tag = 37
    epoch_tag = epoch_tag_for_boot_id(BOOT_ID)
    payload = struct.pack("<BBH", 0, 0, 1)
    if mismatch == "session":
        session_tag = 38
    elif mismatch == "epoch":
        epoch_tag = (epoch_tag + 1) & 0xFFFFFFFF
    elif mismatch == "context":
        payload = struct.pack("<BBH", 0, 0, 2)
    elif mismatch == "applied_pwm":
        payload = struct.pack("<BBH", 0, 1, 1)
    elif mismatch == "result":
        payload = struct.pack("<BBH", 1, 0, 1)
    elif mismatch == "message_type":
        kind = MessageType.ARM_ACK
        payload = struct.pack("<BBH", 0, 1, 1)
    wrong = codec.encode_message(
        kind, session_tag=session_tag, epoch_tag=epoch_tag,
        command_id=2, payload=payload,
    )
    right = ack_frame(codec, MessageType.APPLY_ACK, command=2,
                      payload=struct.pack("<BBH", 0, 0, 1))
    session, _, _, _ = make_session(tmp_path, monkeypatch, [hello, arm, wrong, right])
    session.send_stage_pwm(0, "stage-uuid", "session-uuid", stage_index=0)

    if mismatch in {"context", "applied_pwm", "result"}:
        # A matching command/session/epoch with a contradictory apply result
        # is not an unrelated stale frame; fail closed and never recover on a
        # later apparently-good ACK for the same pending command.
        with pytest.raises(RuntimeError, match="APPLY_ACK rejected"):
            session.poll_apply_ack(0.0)
        assert session._failed is True
        assert session._pending is not None
        with pytest.raises(RuntimeError, match="fail-closed"):
            session.poll_apply_ack(0.0)
    else:
        # Wrong session/epoch or wrong message type is unrelated traffic and
        # may be ignored while the exact pending ACK remains unresolved.
        assert session.poll_apply_ack(0.0) is None
        assert session._pending is not None
        assert session.poll_apply_ack(0.0)[0] == 0
        assert session._pending is None


def test_protocol_session_partial_pwm_write_is_unknown_and_fail_closed(tmp_path, monkeypatch):
    codec = ProtocolV1Codec(MAGIC_FIXTURE, VERSION_FIXTURE)
    hello, arm = handshake_frames(codec)
    transport = MockTransport()
    original_send = transport.send

    def partial_pwm_send(frame):
        message = codec.decode(frame).message
        if message["kind"] == "PWM_SET":
            transport.sent.append(bytes(frame[:3]))
            raise OSError("injected partial write")
        original_send(frame)

    transport.send = partial_pwm_send
    session, _, _, evidence = make_session(
        tmp_path, monkeypatch, [hello, arm], transport=transport
    )
    with pytest.raises(RuntimeError, match="write/flush outcome unknown"):
        session.send_stage_pwm(0, "stage-uuid", "session-uuid", stage_index=0)

    assert session._failed is True
    assert transport.sent[-1] and len(transport.sent[-1]) == 3
    events, _ = evidence._read()
    pwm_intent = next(
        event for event in events
        if event["event"] == "FRAME_TX_INTENT"
        and event["payload"]["kind"] == "PWM_SET"
    )
    pwm_error = next(
        event for event in events
        if event["event"] == "FRAME_TX_ERROR"
        and event["payload"]["kind"] == "PWM_SET"
    )
    assert pwm_intent["payload"]["intent_journal_sha256"]
    assert pwm_error["payload"]["outcome"] == "UNKNOWN"
    sent_before = list(transport.sent)
    with pytest.raises(RuntimeError, match="fail-closed"):
        session.send_stage_pwm(1, "next-stage", "session-uuid", stage_index=1)
    assert transport.sent == sent_before


def test_protocol_session_duplicate_previous_ack_cannot_release_next_stage(
    tmp_path, monkeypatch
):
    codec = ProtocolV1Codec(MAGIC_FIXTURE, VERSION_FIXTURE)
    hello, arm = handshake_frames(codec)
    first_ack = ack_frame(codec, MessageType.APPLY_ACK, command=2,
                          payload=struct.pack("<BBH", 0, 0, 1))
    second_ack = ack_frame(codec, MessageType.APPLY_ACK, command=3,
                           payload=struct.pack("<BBH", 0, 1, 2))
    session, _, _, _ = make_session(
        tmp_path, monkeypatch, [hello, arm, first_ack, first_ack, second_ack]
    )
    session.send_stage_pwm(0, "stage-zero", "session-uuid", stage_index=0)
    assert session.poll_apply_ack(0.0)[0] == 0

    session.send_stage_pwm(1, "stage-one", "session-uuid", stage_index=1)
    assert session.poll_apply_ack(0.0) is None
    assert session._pending is not None
    assert session.poll_apply_ack(0.0)[0] == 1
    assert session._pending is None


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

        def __init__(self):
            self.events = []

        def latch_abort(self, reason):
            self.events.append("LATCH")

        def send_stage_pwm(self, pwm, stage_context_id, measurement_session_id, stage_index=None):
            return "2026-11-04T14:00:00.000Z"

        def poll_apply_ack(self, timeout_s=0.0):
            clock.ns = now_ns
            return 0, "2026-11-04T14:00:00.010Z", ack_ns

    clock = Clock()
    stops = []
    adapter = Adapter()
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
        lambda: (adapter.events.append("STOP"), stops.append("STOP")),
        lambda: None, clock, protocol_session=adapter,
    )
    controller.startup_recover()
    controller.start()
    assert controller.poll() == SequenceState.FAULT
    assert stops == ["STOP"]
    assert adapter.events == ["LATCH", "STOP"]
    assert expected_fault in str(controller._last_fault)


def test_sequence_controller_requires_callbacks_or_v1_session(tmp_path):
    from measurement_310.engine import SequenceController
    from raw_log_v2 import RawLogV2Writer

    with pytest.raises(ValueError, match="legacy send_pwm and poll_ack"):
        SequenceController(
            RawLogV2Writer(tmp_path), {}, None, lambda: None, None,
        )


def test_protocol_session_latch_abort_prevents_pending_command_reuse(tmp_path, monkeypatch):
    codec = ProtocolV1Codec(MAGIC_FIXTURE, VERSION_FIXTURE)
    hello, arm = handshake_frames(codec)
    order = []
    stop_frames = []

    def independent_stop_writer(frame):
        order.append("STOP_WRITE")
        stop_frames.append(frame)

    session, transport, _, _ = make_session(
        tmp_path, monkeypatch, [hello, arm], stop_writer=independent_stop_writer
    )
    session.send_stage_pwm(0, "stage-uuid", "session-uuid", stage_index=0)
    assert session._pending is not None
    session.latch_abort("ACK timeout")
    assert session._failed is True
    assert session._pending is None
    original_append = session.evidence.append

    def traced_append(event, payload, **kwargs):
        if event == "STOP_TX_ATTEMPT":
            order.append("STOP_EVIDENCE")
        return original_append(event, payload, **kwargs)

    session.evidence.append = traced_append
    session.send_stop_best_effort(stop_reason=StopReason.OPERATOR_REQUEST, stop_request_id=7)
    assert order == ["STOP_WRITE", "STOP_EVIDENCE"]
    assert len(stop_frames) == 1
    assert session.codec.decode(stop_frames[0]).message["kind"] == "STOP_REQ"
    assert [session.codec.decode(frame).message["kind"] for frame in transport.sent] == [
        "HELLO", "ARM", "PWM_SET"
    ]
    with pytest.raises(RuntimeError, match="fail-closed"):
        session.poll_apply_ack(0.0)
    with pytest.raises(RuntimeError, match="fail-closed"):
        session.send_stage_pwm(1, "next-stage-uuid", "session-uuid", stage_index=1)
    # STOP was dispatched through the injected independent writer above;
    # it must not be appended to the normal PWM/session transport.
    assert [session.codec.decode(frame).message["kind"] for frame in transport.sent] == [
        "HELLO", "ARM", "PWM_SET"
    ]


def test_stop_request_retry_reuses_byte_identical_frame_and_both_ids(tmp_path, monkeypatch):
    codec = ProtocolV1Codec(MAGIC_FIXTURE, VERSION_FIXTURE)
    writes = []
    fail_once = {"value": True}

    def stop_writer(frame):
        writes.append(bytes(frame))
        if fail_once["value"]:
            fail_once["value"] = False
            raise OSError("uncertain partial STOP write")

    session, _, _, evidence = make_session(tmp_path, monkeypatch, [], stop_writer=stop_writer)
    session.latch_abort("operator abort")
    with pytest.raises(RuntimeError, match="outcome unknown"):
        session.send_stop_best_effort(stop_reason=StopReason.OPERATOR_REQUEST, stop_request_id=9)

    session.send_stop_best_effort(stop_reason=StopReason.OPERATOR_REQUEST, stop_request_id=9)
    assert len(writes) == 2
    assert writes[0] == writes[1]
    decoded = codec.decode(writes[0]).message
    assert decoded["kind"] == "STOP_REQ"
    assert codec.decode(writes[1]).message["command_id"] == decoded["command_id"]
    assert codec.decode(writes[1]).message["stop_request_id"] == decoded["stop_request_id"] == 9

    events, _ = evidence._read()
    stop_events = [event["event"] for event in events if event["event"].startswith("STOP_TX")]
    assert stop_events == ["STOP_TX_ERROR", "STOP_TX_ATTEMPT"]


def test_stop_request_id_cannot_be_reused_for_a_different_reason(tmp_path, monkeypatch):
    codec = ProtocolV1Codec(MAGIC_FIXTURE, VERSION_FIXTURE)
    writes = []
    session, _, _, _ = make_session(
        tmp_path, monkeypatch, [], stop_writer=lambda frame: writes.append(bytes(frame))
    )
    session.latch_abort("operator abort")
    session.send_stop_best_effort(stop_reason=StopReason.OPERATOR_REQUEST, stop_request_id=11)
    with pytest.raises(RuntimeError, match="different logical STOP"):
        session.send_stop_best_effort(stop_reason=StopReason.ACK_TIMEOUT, stop_request_id=11)
    assert len(writes) == 1
    assert codec.decode(writes[0]).message["stop_reason"] == 1


@pytest.mark.parametrize("invalid_reason", [0, 10, 254, 256, True])
def test_stop_request_rejects_unassigned_reason_codes(tmp_path, monkeypatch, invalid_reason):
    writes = []
    session, _, _, _ = make_session(
        tmp_path, monkeypatch, [], stop_writer=lambda frame: writes.append(bytes(frame))
    )
    session.latch_abort("operator abort")
    with pytest.raises(ValueError, match="assigned StopReason"):
        session.send_stop_best_effort(stop_reason=invalid_reason, stop_request_id=3)
    assert writes == []


def test_stop_request_refuses_to_share_command_transport(tmp_path, monkeypatch):
    codec = ProtocolV1Codec(MAGIC_FIXTURE, VERSION_FIXTURE)
    session, transport, _, _ = make_session(tmp_path, monkeypatch, [])
    session.latch_abort("operator abort")
    with pytest.raises(RuntimeError, match="independent STOP writer"):
        session.send_stop_best_effort(stop_reason=StopReason.OPERATOR_REQUEST, stop_request_id=1)
    assert transport.sent == []
