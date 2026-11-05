import json
import shutil

import pytest

from measurement_310.evidence_bundle import (
    EvidenceBundleError,
    verify_evidence_bundle,
    write_evidence_bundle_manifest,
)
from measurement_310.protocol_v1_session import TransportEvidenceJournal


def make_bundle(tmp_path):
    session_id = "f61b4044-e787-4e7b-80fa-ab2f7ea3c6ab"
    package = tmp_path / "LOG-0001"
    package.mkdir()
    (package / "manifest.json").write_text(json.dumps({
        "measurement_session_id": session_id,
        "schema_name": "mini4wd.rawlog",
        "schema_version": "2.0.0",
    }) + "\n")
    (package / "records.jsonl").write_text(
        json.dumps({"record_type": "SESSION_EVENT", "record_seq": 1}) + "\n"
    )
    evidence_dir = tmp_path / ".transport-evidence" / session_id
    evidence_dir.mkdir(parents=True)
    journal = TransportEvidenceJournal(evidence_dir / "transport-evidence-v1.jsonl")
    journal.append(
        "HELLO_ACK_MATCHED", {"boot_id64": 123},
        measurement_session_id=session_id, direction="device_to_host",
    )
    return session_id, package, journal


def test_companion_manifest_binds_rawlog_and_evidence_for_backup_restore(tmp_path):
    session_id, package, journal = make_bundle(tmp_path)
    manifest_path = write_evidence_bundle_manifest(package, journal, session_id)
    assert manifest_path.name == "bundle-manifest.json"
    body = verify_evidence_bundle(package, journal, session_id)
    assert body["measurement_session_id"] == session_id
    assert body["evidence_event_count"] == 1

    restored_root = tmp_path / "restored"
    restored_root.mkdir()
    restored_package = restored_root / package.name
    restored_evidence = restored_root / ".transport-evidence" / session_id
    shutil.copytree(package, restored_package)
    restored_evidence.parent.mkdir(parents=True)
    shutil.copytree(journal.path.parent, restored_evidence)
    restored_journal = TransportEvidenceJournal(
        restored_evidence / "transport-evidence-v1.jsonl"
    )
    restored = verify_evidence_bundle(restored_package, restored_journal, session_id)
    assert restored["evidence_chain_head"] == body["evidence_chain_head"]


def test_companion_verifier_detects_rawlog_or_evidence_tampering(tmp_path):
    session_id, package, journal = make_bundle(tmp_path)
    write_evidence_bundle_manifest(package, journal, session_id)
    (package / "records.jsonl").write_text("{}\n")
    with pytest.raises(EvidenceBundleError, match="RawLog package checksum"):
        verify_evidence_bundle(package, journal, session_id)


def test_companion_manifest_rejects_extra_rawlog_package_files(tmp_path):
    session_id, package, journal = make_bundle(tmp_path)
    (package / "unexpected.bin").write_bytes(b"not part of RawLog v2")
    with pytest.raises(EvidenceBundleError, match="exactly manifest.json"):
        write_evidence_bundle_manifest(package, journal, session_id)
