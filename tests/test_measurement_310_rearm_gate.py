import json
import pytest

from measurement_310.rearm_gate import (
    AckIdentity, ActuationRearmGate, ActuationSafetyJournal, CommandIdentity,
    JournalUntrusted, RearmGateError, WriteFlushStatus,
)


def command(**changes):
    values = dict(command_id="cmd-001", command_type="PWM", session_id="session-A",
                  boot_id64=0x123456789ABCDEF0, stage_context_id="stage-context-A")
    values.update(changes)
    return CommandIdentity(**values)


def ack(**changes):
    values = dict(command_id="cmd-001", command_type="PWM", session_id="session-A",
                  boot_id64=0x123456789ABCDEF0, stage_context_id="stage-context-A")
    values.update(changes)
    return AckIdentity(**values)


def make_gate(path):
    journal = ActuationSafetyJournal(path)
    return journal, ActuationRearmGate(journal)


def arm(gate, calls, *, recovered=True, decision="operator-1", safe=True):
    return gate.arm_if_allowed(
        rawlog_recovery_succeeded=recovered, operator_decision_id=decision,
        device_safe_state_confirmed=safe,
        send_nonzero=lambda: calls.append("NONZERO") or "sent",
    )


def test_rawlog_recovery_alone_never_authorizes_rearm(tmp_path):
    _, gate = make_gate(tmp_path / "actuation.jsonl")
    calls = []
    decision, sent = arm(gate, calls, decision=None, safe=False)
    assert not decision.allowed
    assert sent is None
    assert calls == []


@pytest.mark.parametrize("crash_point", [
    "after_intent",
    "after_write_attempt_before_result",
    "after_write_result_unknown",
    "after_write_result_success_before_ack",
    "after_ack_before_terminal",
])
def test_restart_at_each_incomplete_command_boundary_fails_closed(tmp_path, crash_point):
    path = tmp_path / f"{crash_point}.jsonl"
    journal = ActuationSafetyJournal(path)
    identity = command()
    journal.record_intent(identity)
    if crash_point == "after_write_result_unknown":
        journal.record_write_flush(identity, WriteFlushStatus.UNKNOWN)
    elif crash_point in {"after_write_result_success_before_ack", "after_ack_before_terminal"}:
        journal.record_write_flush(identity, WriteFlushStatus.SUCCEEDED)
        if crash_point == "after_ack_before_terminal":
            assert journal.record_ack(identity, ack())

    # New objects model process restart; no in-memory state is carried forward.
    _, restarted_gate = make_gate(path)
    calls = []
    decision, sent = arm(restarted_gate, calls)
    assert not decision.allowed
    assert sent is None
    assert calls == []
    assert identity.command_id in decision.reason


@pytest.mark.parametrize("status", [WriteFlushStatus.FAILED, WriteFlushStatus.UNKNOWN])
def test_failed_or_unknown_write_flush_blocks_ack_and_rearm(tmp_path, status):
    journal, gate = make_gate(tmp_path / "actuation.jsonl")
    identity = command()
    journal.record_intent(identity)
    journal.record_write_flush(identity, status)
    assert not journal.record_ack(identity, ack())
    calls = []
    decision, sent = arm(gate, calls)
    assert not decision.allowed
    assert sent is None
    assert calls == []


def test_ack_requires_exact_command_session_epoch_and_context(tmp_path):
    journal, gate = make_gate(tmp_path / "actuation.jsonl")
    identity = command()
    journal.record_intent(identity)
    journal.record_write_flush(identity, WriteFlushStatus.SUCCEEDED)
    assert not journal.record_ack(identity, ack(session_id="other"))
    assert not journal.record_ack(identity, ack(boot_id64=0x9ABCDEF0))
    assert not journal.record_ack(identity, ack(stage_context_id="other-context"))
    calls = []
    decision, sent = arm(gate, calls)
    assert not decision.allowed
    assert sent is None
    assert calls == []


def test_exact_ack_still_requires_terminal_safe_and_operator_confirmation(tmp_path):
    journal, gate = make_gate(tmp_path / "actuation.jsonl")
    identity = command()
    journal.record_intent(identity)
    journal.record_write_flush(identity, WriteFlushStatus.SUCCEEDED)
    assert journal.record_ack(identity, ack())
    calls = []
    decision, sent = arm(gate, calls)
    assert not decision.allowed and sent is None and calls == []
    with pytest.raises(ValueError, match="operator_decision_id"):
        journal.record_terminal_safe(identity, operator_decision_id="", device_safe_state_confirmed=True)
    with pytest.raises(ValueError, match="safe state"):
        journal.record_terminal_safe(identity, operator_decision_id="operator-1", device_safe_state_confirmed=False)


def test_unknown_outcome_requires_explicit_operator_reconciliation(tmp_path):
    journal, gate = make_gate(tmp_path / "actuation.jsonl")
    identity = command()
    journal.record_intent(identity)
    journal.record_write_flush(identity, WriteFlushStatus.UNKNOWN)
    journal.record_terminal_safe(
        identity, operator_decision_id="approved-physical-state-check-001",
        device_safe_state_confirmed=True,
    )
    calls = []
    decision, sent = arm(gate, calls)
    assert decision.allowed and sent == "sent"
    assert calls == ["NONZERO"]


def test_complete_ack_path_still_requires_separate_safe_state_confirmation(tmp_path):
    journal, gate = make_gate(tmp_path / "actuation.jsonl")
    identity = command()
    journal.record_intent(identity)
    journal.record_write_flush(identity, WriteFlushStatus.SUCCEEDED)
    assert journal.record_ack(identity, ack())
    journal.record_terminal_safe(
        identity, operator_decision_id="operator-safe-check-002",
        device_safe_state_confirmed=True,
    )
    calls = []
    decision, sent = arm(gate, calls)
    assert decision.allowed and sent == "sent"
    assert calls == ["NONZERO"]


def test_rawlog_recovery_failure_blocks_clean_actuation_history(tmp_path):
    journal, gate = make_gate(tmp_path / "actuation.jsonl")
    identity = command()
    journal.record_intent(identity)
    journal.record_write_flush(identity, WriteFlushStatus.SUCCEEDED)
    journal.record_ack(identity, ack())
    journal.record_terminal_safe(
        identity, operator_decision_id="operator-3", device_safe_state_confirmed=True,
    )
    calls = []
    decision, sent = arm(gate, calls, recovered=False)
    assert not decision.allowed and sent is None and calls == []


def test_torn_or_tampered_journal_blocks_rearm(tmp_path):
    path = tmp_path / "actuation.jsonl"
    journal, gate = make_gate(path)
    journal.record_intent(command())
    with path.open("ab") as stream:
        stream.write(b'{"torn":')
    calls = []
    decision, sent = arm(gate, calls)
    assert not decision.allowed and "untrusted" in decision.reason
    assert sent is None and calls == []


def test_command_id_reuse_and_out_of_order_events_are_rejected(tmp_path):
    journal = ActuationSafetyJournal(tmp_path / "actuation.jsonl")
    identity = command()
    with pytest.raises(RearmGateError):
        journal.record_write_flush(identity, WriteFlushStatus.SUCCEEDED)
    journal.record_intent(identity)
    with pytest.raises(RearmGateError, match="reuse"):
        journal.record_intent(identity)


def test_operator_reconciliation_is_bound_to_exact_command(tmp_path):
    journal = ActuationSafetyJournal(tmp_path / "actuation.jsonl")
    identity = command()
    journal.record_intent(identity)
    with pytest.raises(RearmGateError):
        journal.record_terminal_safe(
            command(command_id="other"), operator_decision_id="operator-4",
            device_safe_state_confirmed=True,
        )


def test_ack_identity_rejects_bool_epoch_even_when_integer_one(tmp_path):
    with pytest.raises(ValueError, match="boot_id64"):
        AckIdentity("cmd-001", "PWM", "session-A", True, "stage-context-A")


def test_short_write_torn_tail_blocks_after_restart(tmp_path, monkeypatch):
    import os
    path = tmp_path / "partial.jsonl"
    journal, _ = make_gate(path)
    original_write = os.write

    def short_write(fd, data):
        if data.endswith(b"\\n"):
            return original_write(fd, data[:-1])
        return original_write(fd, data)

    monkeypatch.setattr("measurement_310.rearm_gate.os.write", short_write)
    with pytest.raises(RearmGateError, match="short journal append"):
        journal.record_intent(command())
    monkeypatch.setattr("measurement_310.rearm_gate.os.write", original_write)
    _, restarted_gate = make_gate(path)
    calls = []
    decision, sent = arm(restarted_gate, calls)
    assert not decision.allowed
    assert "untrusted" in decision.reason
    assert sent is None and calls == []


@pytest.mark.parametrize("failed_event", ["INTENT", "WRITE_FLUSH", "ACK_MATCHED"])
def test_fsync_failure_at_each_preterminal_evidence_boundary_fails_closed(
    tmp_path, monkeypatch, failed_event
):
    import os
    path = tmp_path / f"{failed_event}.jsonl"
    journal, _ = make_gate(path)
    identity = command()
    if failed_event != "INTENT":
        journal.record_intent(identity)
    if failed_event == "ACK_MATCHED":
        journal.record_write_flush(identity, WriteFlushStatus.SUCCEEDED)

    original_fsync = os.fsync
    calls = {"count": 0}

    def fail_first_fsync(fd):
        calls["count"] += 1
        if calls["count"] == 1:
            raise OSError("injected fsync failure")
        return original_fsync(fd)

    monkeypatch.setattr("measurement_310.rearm_gate.os.fsync", fail_first_fsync)
    with pytest.raises(RearmGateError, match="durability uncertain"):
        if failed_event == "INTENT":
            journal.record_intent(identity)
        elif failed_event == "WRITE_FLUSH":
            journal.record_write_flush(identity, WriteFlushStatus.SUCCEEDED)
        else:
            assert journal.record_ack(identity, ack())
    monkeypatch.setattr("measurement_310.rearm_gate.os.fsync", original_fsync)

    # The append may or may not survive a crash; either valid prefix is unsafe.
    _, restarted_gate = make_gate(path)
    calls_sent = []
    decision, sent = arm(restarted_gate, calls_sent)
    assert not decision.allowed
    assert sent is None and calls_sent == []


def test_intent_is_fsynced_before_send_callback_and_write_result_after(tmp_path, monkeypatch):
    import os
    journal = ActuationSafetyJournal(tmp_path / "actuation.jsonl")
    events = []
    original_fsync = os.fsync

    def observed_fsync(fd):
        events.append("fsync")
        return original_fsync(fd)

    monkeypatch.setattr("measurement_310.rearm_gate.os.fsync", observed_fsync)
    result = journal.intent_then_send(command(), lambda: events.append("send") or "sent")
    assert result == "sent"
    assert events == ["fsync", "fsync", "send", "fsync", "fsync"]
    assert journal.recover()["cmd-001"].write_flush is WriteFlushStatus.SUCCEEDED


def test_intent_fsync_failure_suppresses_send_and_callback_exception_is_unknown(tmp_path, monkeypatch):
    import os
    journal = ActuationSafetyJournal(tmp_path / "actuation.jsonl")
    sent = []
    original_fsync = os.fsync

    def fail_fsync(fd):
        raise OSError("intent fsync failure")

    monkeypatch.setattr("measurement_310.rearm_gate.os.fsync", fail_fsync)
    with pytest.raises(RearmGateError, match="durability uncertain"):
        journal.intent_then_send(command(), lambda: sent.append("sent"))
    assert sent == []

    monkeypatch.setattr("measurement_310.rearm_gate.os.fsync", original_fsync)
    journal = ActuationSafetyJournal(tmp_path / "uncertain.jsonl")
    with pytest.raises(OSError, match="partial write"):
        journal.intent_then_send(
            command(), lambda: (_ for _ in ()).throw(OSError("partial write / flush uncertain"))
        )
    state = journal.recover()["cmd-001"]
    assert state.write_flush is WriteFlushStatus.UNKNOWN


def test_symlinked_actuation_journal_blocks_rearm(tmp_path):
    target = tmp_path / "trusted.jsonl"
    ActuationSafetyJournal(target).record_intent(command())
    link = tmp_path / "actuation.jsonl"
    link.symlink_to(target)
    _, gate = make_gate(link)
    calls = []
    decision, sent = arm(gate, calls)
    assert not decision.allowed
    assert "symlink" in decision.reason
    assert sent is None and calls == []


def test_unreadable_actuation_journal_blocks_rearm(tmp_path, monkeypatch):
    from pathlib import Path
    path = tmp_path / "actuation.jsonl"
    ActuationSafetyJournal(path).record_intent(command())
    original_read_bytes = Path.read_bytes

    def fail_read(self):
        if self == path:
            raise PermissionError("injected permission failure")
        return original_read_bytes(self)

    monkeypatch.setattr(Path, "read_bytes", fail_read)
    _, gate = make_gate(path)
    calls = []
    decision, sent = arm(gate, calls)
    assert not decision.allowed
    assert "unavailable" in decision.reason
    assert sent is None and calls == []
