import pytest

from measurement_310.command_intent import (
    AckIdentity,
    CommandIdentity,
    DurableIntentJournal,
)
from measurement_310.evidence_gate import EvidenceGate


def command():
    return CommandIdentity("cmd-1", "PWM", "session-1", 0x123456789ABCDEF0, "ctx-1")


def matching_ack():
    return AckIdentity("cmd-1", "PWM", "session-1", 0x123456789ABCDEF0, "ctx-1")


def test_intent_failure_prevents_send_and_attempts_stop(tmp_path, monkeypatch):
    journal = DurableIntentJournal(tmp_path / "intent.jsonl")
    sent, stopped = [], []
    monkeypatch.setattr("measurement_310.command_intent.os.fsync",
                        lambda fd: (_ for _ in ()).throw(OSError("fsync fault")))
    gate = EvidenceGate(journal, lambda *args: sent.append(args),
                        lambda: stopped.append(True), lambda record: None)
    outcome = gate.send(command(), b"PWM-NONZERO", "now")
    assert not outcome.sent
    assert outcome.stopped_attempted
    assert sent == []
    assert stopped == [True]
    assert not gate.send(command(), b"PWM-NONZERO", "later").sent


def test_ack_evidence_failure_latches_gate_and_attempts_stop(tmp_path):
    sent, stopped = [], []
    def fail_evidence(record):
        raise OSError("evidence fsync failure")

    gate = EvidenceGate(DurableIntentJournal(tmp_path / "intent.jsonl"),
                        lambda *args: sent.append(args),
                        lambda: stopped.append(True), fail_evidence)
    assert gate.send(command(), b"PWM-NONZERO", "now").sent
    assert not gate.accept_ack(matching_ack(), {"kind": "ACK"})
    assert stopped == [True]
    assert not gate.send(
        CommandIdentity("cmd-2", "PWM", "session-1", 0x123456789ABCDEF0, "ctx-2"),
        b"PWM-NONZERO", "later").sent
    assert len(sent) == 1


def test_ack_mismatch_does_not_persist_or_advance(tmp_path):
    evidence, sent = [], []
    gate = EvidenceGate(DurableIntentJournal(tmp_path / "intent.jsonl"),
                        lambda *args: sent.append(args), lambda: None,
                        lambda record: evidence.append(record))
    assert gate.send(command(), b"PWM-NONZERO", "now").sent
    wrong = AckIdentity("cmd-1", "PWM", "other-session",
                        0x123456789ABCDEF0, "ctx-1")
    assert not gate.accept_ack(wrong, {"kind": "ACK"})
    assert evidence == []
    assert not gate.failed


def test_expired_ack_is_rejected(tmp_path):
    evidence = []
    gate = EvidenceGate(DurableIntentJournal(tmp_path / "intent.jsonl"),
                        lambda *args: None, lambda: None,
                        lambda record: evidence.append(record))
    assert gate.send(command(), b"PWM-NONZERO", "now").sent
    gate.expire("cmd-1")
    assert not gate.accept_ack(matching_ack(), {"kind": "ACK"})
    assert evidence == []


def test_transport_failure_latches_and_does_not_claim_send(tmp_path):
    stopped = []
    gate = EvidenceGate(DurableIntentJournal(tmp_path / "intent.jsonl"),
                        lambda *args: (_ for _ in ()).throw(OSError("write failed")),
                        lambda: stopped.append(True), lambda record: None)
    outcome = gate.send(command(), b"PWM-NONZERO", "now")
    assert not outcome.sent
    assert gate.failed
    assert stopped == []
