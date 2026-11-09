import hashlib
import uuid

from measurement_310.protocol_v1_session import TransportEvidenceJournal
from measurement_310.protocol_v2 import (
    PROTOCOL_V2_MAGIC, PROTOCOL_V2_VERSION, ProtocolV2Codec,
)
from measurement_310.protocol_v2_session import ProtocolV2HostSession


def test_evidence_append_many_preserves_hash_chain_and_event_ids(tmp_path):
    journal = TransportEvidenceJournal(tmp_path / "transport-evidence-v1.jsonl")
    session_id = str(uuid.uuid4())
    first_id = journal.append(
        "SESSION_STARTED", {"ordinal": 0},
        measurement_session_id=session_id,
    )
    entries = [
        {
            "event": "RX_BYTES",
            "payload": {"ordinal": 1},
            "measurement_session_id": session_id,
            "direction": "device_to_host",
            "event_id": str(uuid.uuid4()),
            "host_event_at_utc": "2026-11-08T00:00:00.000Z",
            "host_event_monotonic_ns": 100,
        },
        {
            "event": "ADC_BATCH_ACCEPTED",
            "payload": {"ordinal": 2},
            "measurement_session_id": session_id,
            "direction": "device_to_host",
            "event_id": str(uuid.uuid4()),
            "host_event_at_utc": "2026-11-08T00:00:00.001Z",
            "host_event_monotonic_ns": 101,
        },
    ]

    returned_ids = journal.append_many(entries)
    events, chain_head = journal._read()

    assert returned_ids == [entry["event_id"] for entry in entries]
    assert [event["event"] for event in events] == [
        "SESSION_STARTED", "RX_BYTES", "ADC_BATCH_ACCEPTED"
    ]
    assert [event["event_id"] for event in events] == [first_id, *returned_ids]
    first_hash = hashlib.sha256(journal._canonical(events[0])).hexdigest()
    second_hash = hashlib.sha256(journal._canonical(events[1])).hexdigest()
    assert events[1]["previous_hash"] == first_hash
    assert events[2]["previous_hash"] == second_hash
    assert chain_head == journal._cached_chain_head
    assert events[1]["host_event_monotonic_ns"] == 100
    assert events[2]["host_event_monotonic_ns"] == 101


class FakeEvidence:
    def __init__(self):
        self.transactions = []
        self.single_events = []

    def append_many(self, entries):
        self.transactions.append(list(entries))
        return [entry["event_id"] for entry in entries]

    def append(self, event, payload, **kwargs):
        self.single_events.append((event, payload, kwargs))
        return str(uuid.uuid4())


def make_session(evidence):
    codec = ProtocolV2Codec(PROTOCOL_V2_MAGIC, PROTOCOL_V2_VERSION)
    session = ProtocolV2HostSession(
        transport=object(), codec=codec, intent_journal=object(),
        evidence_journal=evidence, stop_writer=lambda _frame: None,
    )
    session.measurement_session_id = str(uuid.uuid4())
    session.boot_id64 = 0x3105102026110601
    return session


def test_protocol_telemetry_evidence_flushes_in_bounded_ten_batch_transactions():
    evidence = FakeEvidence()
    session = make_session(evidence)

    for index in range(9):
        session._append("RX_BYTES", raw_b64=f"rx-{index}")
        session._append("FRAME_RX_DECODED", message_kind="ADC_BATCH",
                        command_id=index, raw_frame_base64=f"frame-{index}")
        session._append("ADC_BATCH_ACCEPTED", first_sample_sequence64=index * 12,
                        sample_count=12)

    assert evidence.transactions == []
    assert len(session._pending_evidence_events) == 27

    session._append("RX_BYTES", raw_b64="rx-9")
    session._append("FRAME_RX_DECODED", message_kind="ADC_BATCH",
                    command_id=9, raw_frame_base64="frame-9")
    session._append("ADC_BATCH_ACCEPTED", first_sample_sequence64=108,
                    sample_count=12)

    assert len(evidence.transactions) == 1
    assert len(evidence.transactions[0]) == 30
    assert session._pending_evidence_events == []
    assert session._pending_telemetry_batches == 0


def test_control_evidence_flushes_pending_telemetry_before_control_event():
    evidence = FakeEvidence()
    session = make_session(evidence)
    session._append("RX_BYTES", raw_b64="rx-pending")

    session._append("FRAME_TX_INTENT", kind="DISARM", command_id=9)

    assert len(evidence.transactions) == 1
    assert evidence.transactions[0][0]["event"] == "RX_BYTES"
    assert len(evidence.single_events) == 1
    assert evidence.single_events[0][0] == "FRAME_TX_INTENT"


def test_stop_evidence_does_not_flush_pending_telemetry_on_stop_path():
    evidence = FakeEvidence()
    session = make_session(evidence)
    session._append("RX_BYTES", raw_b64="rx-pending")

    session._append("STOP_TX_ATTEMPT", stop_request_id=1, outcome="HOST_WRITE_COMPLETED")

    assert evidence.transactions == []
    assert evidence.single_events == []
    assert len(session._pending_evidence_events) == 2

    session.flush_evidence()
    assert len(evidence.transactions) == 1
    assert [entry["event"] for entry in evidence.transactions[0]] == [
        "RX_BYTES", "STOP_TX_ATTEMPT"
    ]



def test_production_pwm_send_requires_bound_rearm_root(tmp_path):
    evidence = FakeEvidence()
    session = make_session(evidence)
    import pytest
    from measurement_310.protocol_v2_session import ProtocolV2SessionError

    with pytest.raises(ProtocolV2SessionError, match="re-arm root is not bound"):
        session.send_stage_pwm(1, str(uuid.uuid4()), str(uuid.uuid4()), stage_index=1)


def test_persistent_rearm_marker_blocks_protocol_v2_nonzero_send(tmp_path):
    evidence = FakeEvidence()
    session = make_session(evidence)
    session._rearm_inhibit_root = tmp_path
    (tmp_path / ".310-rearm-inhibited").write_text(
        "Recovered incomplete work requires explicit reconciliation.\\n"
    )
    import pytest
    from measurement_310.protocol_v2_session import ProtocolV2SessionError

    with pytest.raises(ProtocolV2SessionError, match="automatic re-arm is inhibited"):
        session.send_stage_pwm(1, str(uuid.uuid4()), str(uuid.uuid4()), stage_index=1)
    assert evidence.transactions == []
    assert evidence.single_events == []


def test_symlinked_rearm_marker_blocks_protocol_v2_nonzero_send(tmp_path):
    evidence = FakeEvidence()
    session = make_session(evidence)
    session._rearm_inhibit_root = tmp_path
    target = tmp_path / "target"
    target.write_text("inhibit")
    (tmp_path / ".310-rearm-inhibited").symlink_to(target)
    import pytest
    from measurement_310.protocol_v2_session import ProtocolV2SessionError

    with pytest.raises(ProtocolV2SessionError, match="must not be a symlink"):
        session.send_stage_pwm(1, str(uuid.uuid4()), str(uuid.uuid4()), stage_index=1)
