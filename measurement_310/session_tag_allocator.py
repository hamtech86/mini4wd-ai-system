"""Fail-closed host-side session tag allocator model for 310-5 T01.
Tags are 1..0xFFFFFFFE. A tag is returned only after its allocation record
has been appended and fsynced. A torn/corrupt journal is never repaired.
This is a host filesystem implementation, not proof of target power-loss semantics.
"""
from __future__ import annotations
from dataclasses import dataclass
import fcntl
import hashlib
import json
import os
from pathlib import Path
from typing import Optional

MAX_TAG = 0xFFFFFFFE
FORMAT = "310-session-tag-journal-v1"

class AllocationError(RuntimeError): pass
class JournalUntrusted(AllocationError): pass
class TagExhausted(AllocationError): pass

@dataclass(frozen=True)
class Allocation:
    tag: int
    namespace: str
    ordinal: int
    record_hash: str

def _canonical(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")

def _make_record(namespace: str, ordinal: int, tag: int, previous_hash: str) -> dict:
    body = {"format": FORMAT, "namespace": namespace, "ordinal": ordinal,
            "tag": tag, "previous_hash": previous_hash}
    return {"body": body, "sha256": hashlib.sha256(_canonical(body)).hexdigest()}

def _validate_record(record: dict, namespace: str, ordinal: int,
                     expected_tag: int, previous_hash: str) -> str:
    if not isinstance(record, dict) or set(record) != {"body", "sha256"}:
        raise JournalUntrusted("invalid journal record envelope")
    body = record["body"]
    if not isinstance(body, dict):
        raise JournalUntrusted("journal body is not an object")
    digest = hashlib.sha256(_canonical(body)).hexdigest()
    if not isinstance(record["sha256"], str) or digest != record["sha256"]:
        raise JournalUntrusted("journal record checksum mismatch")
    expected = {"format": FORMAT, "namespace": namespace, "ordinal": ordinal,
                "tag": expected_tag, "previous_hash": previous_hash}
    if body != expected:
        raise JournalUntrusted("journal namespace/chain/ordinal/tag mismatch")
    return digest

class SessionTagAllocator:
    """Append-only allocator. Missing journal requires explicit trusted high-water."""
    def __init__(self, journal_path: os.PathLike | str, namespace: str,
                 *, initial_high_water: Optional[int] = None):
        if not isinstance(namespace, str) or not namespace:
            raise ValueError("namespace must be a non-empty fixed string")
        if initial_high_water is not None and (
            isinstance(initial_high_water, bool) or not isinstance(initial_high_water, int)
            or not 0 <= initial_high_water <= MAX_TAG):
            raise ValueError("initial_high_water outside permitted range")
        self.path = Path(journal_path)
        self.namespace = namespace
        self.initial_high_water = initial_high_water
        self.lock_path = self.path.with_name(self.path.name + ".lock")
        self.anchor_path = self.path.with_name(self.path.name + ".anchor")

    def _initialize_if_missing(self) -> None:
        if self.path.exists(): return
        if self.initial_high_water is None:
            raise JournalUntrusted("journal missing and no trusted high-water supplied")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(self.path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try: os.fsync(fd)
        finally: os.close(fd)
        dfd = os.open(str(self.path.parent), os.O_RDONLY)
        try: os.fsync(dfd)
        finally: os.close(dfd)
        # Bootstrap records are explicit consumed tags, not an editable scalar.
        if self.initial_high_water:
            with open(self.path, "ab", buffering=0) as stream:
                previous = "0" * 64
                for ordinal in range(1, self.initial_high_water + 1):
                    rec = _make_record(self.namespace, ordinal, ordinal, previous)
                    stream.write(_canonical(rec) + b"\n")
                    previous = rec["sha256"]
                os.fsync(stream.fileno())
        high, count, digest = self._read_state()
        self._write_anchor(high, count, digest)

    def _anchor_bytes(self, high: int, count: int, digest: str) -> bytes:
        body = {"format": FORMAT + "-anchor", "namespace": self.namespace,
                "high_water": high, "ordinal": count, "journal_hash": digest}
        return _canonical({"body": body,
                           "sha256": hashlib.sha256(_canonical(body)).hexdigest()}) + b"\\n"

    def _write_anchor(self, high: int, count: int, digest: str,
                      *, fault_at: Optional[str] = None) -> None:
        data = self._anchor_bytes(high, count, digest)
        temp = self.anchor_path.with_name(self.anchor_path.name + ".tmp")
        fd = os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if fault_at == "after_anchor_file_fsync":
                raise OSError("injected after anchor file fsync")
            os.replace(temp, self.anchor_path)
            if fault_at == "after_anchor_replace":
                raise OSError("injected after anchor replace")
            if fault_at == "before_anchor_dir_fsync":
                raise OSError("injected before anchor directory fsync")
            dfd = os.open(str(self.anchor_path.parent), os.O_RDONLY)
            try: os.fsync(dfd)
            finally: os.close(dfd)
        except Exception:
            try: temp.unlink()
            except FileNotFoundError: pass
            raise

    def _verify_anchor(self, high: int, count: int, digest: str) -> None:
        try:
            envelope = json.loads(self.anchor_path.read_text("utf-8"))
            body = envelope["body"]
            expected = self._anchor_bytes(high, count, digest)
            if _canonical(envelope) + b"\\n" != expected:
                raise JournalUntrusted("rollback or mismatch against monotonic anchor")
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
            if isinstance(exc, JournalUntrusted): raise
            raise JournalUntrusted(f"anchor missing/corrupt: {exc}") from exc

    def _read_state(self) -> tuple[int, int, str]:
        try: raw = self.path.read_bytes()
        except OSError as exc: raise JournalUntrusted(f"journal unreadable: {exc}") from exc
        if not raw: return 0, 0, "0" * 64
        if not raw.endswith(b"\n"): raise JournalUntrusted("truncated final journal record")
        high_water, ordinal, previous = 0, 0, "0" * 64
        for line in raw.splitlines():
            ordinal += 1
            try:
                record = json.loads(line.decode("utf-8"))
                body = record["body"]
                tag = body["tag"]
                if isinstance(tag, bool) or not isinstance(tag, int):
                    raise ValueError("tag is not an integer")
                if not 1 <= tag <= MAX_TAG: raise ValueError("tag outside range")
                previous = _validate_record(record, self.namespace, ordinal,
                                            high_water + 1, previous)
            except (ValueError, KeyError, TypeError, UnicodeError, json.JSONDecodeError) as exc:
                raise JournalUntrusted(f"journal validation failed at record {ordinal}: {exc}") from exc
            high_water = tag
        return high_water, ordinal, previous

    def allocate(self, *, fault_at: Optional[str] = None) -> Allocation:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            self._initialize_if_missing()
            high_water, ordinal, previous = self._read_state()
            if not self.anchor_path.exists():
                raise JournalUntrusted("monotonic anchor missing; rollback cannot be excluded")
            self._verify_anchor(high_water, ordinal, previous)
            if high_water >= MAX_TAG: raise TagExhausted("session tag space exhausted; wrap forbidden")
            tag = high_water + 1
            record = _make_record(self.namespace, ordinal + 1, tag, previous)
            line = _canonical(record) + b"\n"
            fd = os.open(str(self.path), os.O_WRONLY | os.O_APPEND)
            try:
                written = os.write(fd, line)
                if written != len(line): raise AllocationError("short append; fail closed")
                if fault_at == "after_journal_write":
                    raise OSError("injected after journal append before fsync")
                os.fsync(fd)
                if fault_at == "after_journal_fsync":
                    raise OSError("injected after journal fsync before anchor update")
            finally: os.close(fd)
            self._write_anchor(tag, ordinal + 1, record["sha256"], fault_at=fault_at)
            return Allocation(tag, self.namespace, ordinal + 1, record["sha256"])
        except OSError as exc:
            raise AllocationError(f"allocation persistence failed: {exc}") from exc
        finally:
            try: fcntl.flock(lock_fd, fcntl.LOCK_UN)
            finally: os.close(lock_fd)
