"""Companion-manifest verification for the external protocol Evidence sidecar.

RawLog v2 remains exactly manifest.json + records.jsonl. This file binds that
unchanged package to its external transport-evidence-v1.jsonl companion.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile

from .protocol_v1_session import TransportEvidenceJournal


FORMAT = "transport-evidence-bundle-v1"
PACKAGE_FILES = ("manifest.json", "records.jsonl")


class EvidenceBundleError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_regular(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise EvidenceBundleError(f"required regular file missing or symlinked: {path.name}")
    return path.read_bytes()


def write_evidence_bundle_manifest(
    rawlog_package_dir: os.PathLike | str,
    evidence_journal: TransportEvidenceJournal,
    measurement_session_id: str,
) -> Path:
    package = Path(rawlog_package_dir)
    if package.is_symlink() or not package.is_dir():
        raise EvidenceBundleError("RawLog package must be a real directory")
    if not isinstance(measurement_session_id, str) or not measurement_session_id:
        raise EvidenceBundleError("measurement_session_id is required")
    files = {name: _read_regular(package / name) for name in PACKAGE_FILES}
    try:
        rawlog_manifest = json.loads(files["manifest.json"].decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise EvidenceBundleError("RawLog manifest is invalid JSON") from exc
    if rawlog_manifest.get("measurement_session_id") != measurement_session_id:
        raise EvidenceBundleError("RawLog package session UUID mismatch")
    evidence_path = evidence_journal.path
    evidence_bytes = _read_regular(evidence_path)
    events, chain_head = evidence_journal._read()
    for event in events:
        event_session = event.get("measurement_session_id")
        if event_session not in (None, measurement_session_id):
            raise EvidenceBundleError("Evidence event belongs to a different measurement session")
    body = {
        "format": FORMAT,
        "schema_version": 1,
        "measurement_session_id": measurement_session_id,
        "rawlog_files": {name: _sha256(files[name]) for name in PACKAGE_FILES},
        "evidence_file": evidence_path.name,
        "evidence_sha256": _sha256(evidence_bytes),
        "evidence_chain_head": chain_head,
        "evidence_event_count": len(events),
    }
    encoded = (json.dumps(body, sort_keys=True, separators=(",", ":")) + "\\n").encode("utf-8")
    parent = evidence_path.parent
    if parent.is_symlink() or not parent.is_dir():
        raise EvidenceBundleError("Evidence sidecar directory must be a real directory")
    fd, temporary = tempfile.mkstemp(prefix=".bundle-manifest-", suffix=".tmp", dir=str(parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            view = memoryview(encoded)
            while view:
                count = stream.write(view)
                if count is None or count <= 0:
                    raise EvidenceBundleError("short companion-manifest write")
                view = view[count:]
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, parent / "bundle-manifest.json")
        dir_fd = os.open(str(parent), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
    return parent / "bundle-manifest.json"


def verify_evidence_bundle(
    rawlog_package_dir: os.PathLike | str,
    evidence_journal: TransportEvidenceJournal,
    measurement_session_id: str,
) -> dict:
    package = Path(rawlog_package_dir)
    if package.is_symlink() or not package.is_dir():
        raise EvidenceBundleError("RawLog package must be a real directory")
    companion = evidence_journal.path.parent / "bundle-manifest.json"
    try:
        body = json.loads(_read_regular(companion).decode("utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise EvidenceBundleError("companion manifest is invalid JSON") from exc
    if (body.get("format") != FORMAT or body.get("schema_version") != 1
            or body.get("measurement_session_id") != measurement_session_id
            or body.get("evidence_file") != evidence_journal.path.name):
        raise EvidenceBundleError("companion manifest identity/schema mismatch")
    files = {name: _read_regular(package / name) for name in PACKAGE_FILES}
    rawlog_manifest = json.loads(files["manifest.json"].decode("utf-8"))
    if rawlog_manifest.get("measurement_session_id") != measurement_session_id:
        raise EvidenceBundleError("restored RawLog package session UUID mismatch")
    actual_hashes = {name: _sha256(files[name]) for name in PACKAGE_FILES}
    if body.get("rawlog_files") != actual_hashes:
        raise EvidenceBundleError("RawLog package checksum mismatch")
    evidence_bytes = _read_regular(evidence_journal.path)
    if body.get("evidence_sha256") != _sha256(evidence_bytes):
        raise EvidenceBundleError("Evidence sidecar checksum mismatch")
    events, chain_head = evidence_journal._read()
    if (body.get("evidence_chain_head") != chain_head
            or body.get("evidence_event_count") != len(events)):
        raise EvidenceBundleError("Evidence hash-chain head/count mismatch")
    for event in events:
        if event.get("measurement_session_id") not in (None, measurement_session_id):
            raise EvidenceBundleError("Evidence event session UUID mismatch")
    return body
