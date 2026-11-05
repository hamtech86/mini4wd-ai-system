import uuid

import pytest

from measurement_310.protocol_v1_session import (
    ProtocolV1SessionError,
    TransportEvidenceJournal,
)


def test_for_session_uses_external_deterministic_sidecar(tmp_path):
    session_id = str(uuid.uuid4())
    journal = TransportEvidenceJournal.for_session(tmp_path, session_id)
    assert journal.path == (
        tmp_path / ".transport-evidence" / session_id / "transport-evidence-v1.jsonl"
    )
    assert journal.path.parent.is_dir()
    assert not (tmp_path / "log-1").exists()


def test_for_session_rejects_noncanonical_session_id(tmp_path):
    with pytest.raises(ProtocolV1SessionError):
        TransportEvidenceJournal.for_session(tmp_path, "not-a-uuid")


def test_for_session_fails_closed_when_directory_fsync_fails(tmp_path, monkeypatch):
    def fail(_path):
        raise OSError("directory fsync unavailable")
    monkeypatch.setattr(TransportEvidenceJournal, "_fsync_directory", staticmethod(fail))
    with pytest.raises(OSError):
        TransportEvidenceJournal.for_session(tmp_path, str(uuid.uuid4()))
