import json
import pytest

from measurement_310.command_intent import (
    AckCorrelator,
    AckIdentity,
    CommandIdentity,
    DurableIntentJournal,
    IntentError,
    IntentUntrusted,
    commit_intent_then_send,
)


def identity(**changes):
    values = dict(command_id="cmd-001", command_type="PWM",
                  session_id="session-A", boot_id64=0x123456789ABCDEF0,
                  stage_context_id="stage-context-A")
    values.update(changes)
    return CommandIdentity(**values)


def ack(**changes):
    values = dict(command_id="cmd-001", command_type="PWM",
                  session_id="session-A", boot_id64=0x123456789ABCDEF0,
                  stage_context_id="stage-context-A")
    values.update(changes)
    return AckIdentity(**values)


def test_intent_is_fsynced_before_send_callback(tmp_path, monkeypatch):
    path = tmp_path / "intent.jsonl"
    journal = DurableIntentJournal(path)
    events = []
    original_fsync = __import__("os").fsync

    def observed_fsync(fd):
        events.append("fsync")
        return original_fsync(fd)

    monkeypatch.setattr("measurement_310.command_intent.os.fsync", observed_fsync)

    def send(command):
        events.append("send")
        assert path.exists()
        assert len(path.read_text().splitlines()) == 1
        return "sent"

    digest, result = commit_intent_then_send(
        journal, identity(), "2026-11-03T11:00:00Z", send)
    assert len(digest) == 64
    assert result == "sent"
    assert events == ["fsync", "fsync", "send"]


def test_intent_journal_hash_chain_and_torn_tail_fail_closed(tmp_path):
    path = tmp_path / "intent.jsonl"
    journal = DurableIntentJournal(path)
    journal.append_intent(identity(), "2026-11-03T11:00:00Z")
    journal.append_intent(identity(command_id="cmd-002"), "2026-11-03T11:00:01Z")
    assert len(path.read_text().splitlines()) == 2
    with path.open("ab") as stream:
        stream.write(b'{"torn":')
    with pytest.raises(IntentUntrusted, match="torn"):
        journal.append_intent(identity(command_id="cmd-003"), "2026-11-03T11:00:02Z")


def test_send_is_never_called_when_intent_commit_fails(tmp_path, monkeypatch):
    journal = DurableIntentJournal(tmp_path / "intent.jsonl")
    called = []
    monkeypatch.setattr("measurement_310.command_intent.os.fsync",
                        lambda fd: (_ for _ in ()).throw(OSError("disk failure")))
    with pytest.raises(IntentError):
        commit_intent_then_send(journal, identity(), "now",
                                lambda command: called.append(command))
    assert called == []


def test_ack_requires_exact_full_identity():
    correlator = AckCorrelator()
    correlator.register(identity())
    assert not correlator.correlate(ack(session_id="other-session"))
    assert not correlator.correlate(ack(boot_id64=0x000000009ABCDEF0))
    assert not correlator.correlate(ack(stage_context_id="other-context"))
    assert not correlator.correlate(ack(command_type="STOP"))
    assert correlator.correlate(ack())
    assert not correlator.correlate(ack())


def test_late_ack_after_expiry_never_correlates():
    correlator = AckCorrelator()
    correlator.register(identity())
    correlator.expire("cmd-001")
    assert not correlator.correlate(ack())


def test_command_id_cannot_be_reused_after_expiry():
    correlator = AckCorrelator()
    correlator.register(identity())
    correlator.expire("cmd-001")
    with pytest.raises(IntentError):
        correlator.register(identity())



@pytest.mark.parametrize("boot_id64", [True, False, -1, 0x10000000000000000, 1.5, "1"])
def test_ack_identity_rejects_invalid_full_epoch(boot_id64):
    with pytest.raises(ValueError, match="boot_id64"):
        ack(boot_id64=boot_id64)


@pytest.mark.parametrize("field", [
    "command_id", "command_type", "session_id", "stage_context_id",
])
def test_ack_identity_rejects_empty_or_non_string_identity_fields(field):
    with pytest.raises(ValueError, match=field):
        ack(**{field: ""})
    with pytest.raises(ValueError, match=field):
        ack(**{field: None})


def test_correlator_rejects_non_ack_objects_without_advancing():
    correlator = AckCorrelator()
    correlator.register(identity())
    assert not correlator.correlate({"command_id": "cmd-001"})
    assert correlator.correlate(ack())



def test_parent_directory_fsync_failure_prevents_send(tmp_path, monkeypatch):
    journal = DurableIntentJournal(tmp_path / "intent.jsonl")
    calls = []
    sent = []

    def fail_directory_fsync(fd):
        calls.append(fd)
        if len(calls) == 2:
            raise OSError("directory fsync failure")

    monkeypatch.setattr("measurement_310.command_intent.os.fsync", fail_directory_fsync)
    with pytest.raises(IntentError, match="intent durability failed"):
        commit_intent_then_send(
            journal, identity(), "2026-11-03T11:00:00Z",
            lambda command: sent.append(command),
        )
    assert len(calls) == 2
    assert sent == []
