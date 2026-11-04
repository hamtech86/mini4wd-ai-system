"""Host-side T04 command intent durability and exact ACK correlation.

This module models host evidence and correlation only. It does not define a
firmware wire format or claim that an ACK proves physical motor state.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
import fcntl
from pathlib import Path
from typing import Callable


class IntentError(RuntimeError):
    pass


class IntentUntrusted(IntentError):
    pass


@dataclass(frozen=True)
class CommandIdentity:
    command_id: str
    command_type: str
    session_id: str
    boot_id64: int
    stage_context_id: str

    def __post_init__(self):
        for name in ("command_id", "command_type", "session_id", "stage_context_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        if (not isinstance(self.boot_id64, int) or isinstance(self.boot_id64, bool)
                or not 0 <= self.boot_id64 <= 0xFFFFFFFFFFFFFFFF):
            raise ValueError("boot_id64 must be uint64")


@dataclass(frozen=True)
class AckIdentity:
    command_id: str
    command_type: str
    session_id: str
    boot_id64: int
    stage_context_id: str

    def __post_init__(self):
        # Validate untrusted ACK fields independently of the trusted command.
        # In particular, bool is an int subclass and True == 1 in Python.
        for name in ("command_id", "command_type", "session_id", "stage_context_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string")
        if (not isinstance(self.boot_id64, int) or isinstance(self.boot_id64, bool)
                or not 0 <= self.boot_id64 <= 0xFFFFFFFFFFFFFFFF):
            raise ValueError("boot_id64 must be uint64")


class DurableIntentJournal:
    """Append-only, fsynced intent journal; malformed/torn tails fail closed."""

    def __init__(self, path: os.PathLike | str):
        self.path = Path(path)

    @staticmethod
    def _canonical(value: dict) -> bytes:
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()

    def append_intent(self, identity: CommandIdentity, created_utc: str) -> str:
        if not isinstance(created_utc, str) or not created_utc:
            raise ValueError("created_utc is required")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.path.with_name(self.path.name + ".lock")
        lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX)
            return self._append_locked(identity, created_utc)
        finally:
            try:
                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            finally:
                os.close(lock_fd)

    def _append_locked(self, identity: CommandIdentity, created_utc: str) -> str:
        previous = self._last_hash()
        body = {
            "record_type": "COMMAND_INTENT",
            "command_id": identity.command_id,
            "command_type": identity.command_type,
            "session_id": identity.session_id,
            "boot_id64": identity.boot_id64,
            "stage_context_id": identity.stage_context_id,
            "created_utc": created_utc,
            "previous_hash": previous,
        }
        digest = hashlib.sha256(self._canonical(body)).hexdigest()
        line = self._canonical({"body": body, "sha256": digest}) + b"\n"
        fd = os.open(str(self.path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            written = os.write(fd, line)
            if written != len(line):
                raise IntentError("short intent append; outcome is uncertain")
            os.fsync(fd)
            # Persist the directory entry as well as the journal bytes. Without
            # this, the first intent file could disappear after power loss even
            # though fsync(file) returned successfully.
            dir_fd = os.open(
                str(self.path.parent),
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError as exc:
            raise IntentError(f"intent durability failed: {exc}") from exc
        finally:
            os.close(fd)
        return digest

    def _last_hash(self) -> str:
        if not self.path.exists():
            return "0" * 64
        raw = self.path.read_bytes()
        if raw and not raw.endswith(b"\n"):
            raise IntentUntrusted("torn intent journal tail")
        previous = "0" * 64
        for number, line in enumerate(raw.splitlines(), 1):
            try:
                envelope = json.loads(line.decode("utf-8"))
                body = envelope["body"]
                digest = hashlib.sha256(self._canonical(body)).hexdigest()
                if envelope["sha256"] != digest or body["previous_hash"] != previous:
                    raise ValueError("hash chain mismatch")
                if body.get("record_type") != "COMMAND_INTENT":
                    raise ValueError("unexpected record type")
                previous = digest
            except (ValueError, KeyError, TypeError, UnicodeError) as exc:
                raise IntentUntrusted(f"invalid intent journal record {number}: {exc}") from exc
        return previous


class AckCorrelator:
    """Only exact identity matches authorize the corresponding host stage."""

    def __init__(self):
        self._pending: dict[str, CommandIdentity] = {}
        self._expired: set[str] = set()

    def register(self, identity: CommandIdentity) -> None:
        if not isinstance(identity, CommandIdentity):
            raise TypeError("identity must be CommandIdentity")
        if identity.command_id in self._pending or identity.command_id in self._expired:
            raise IntentError("command_id has already been used")
        self._pending[identity.command_id] = identity

    def expire(self, command_id: str) -> None:
        if command_id in self._pending:
            del self._pending[command_id]
        self._expired.add(command_id)

    def correlate(self, ack: AckIdentity) -> bool:
        if not isinstance(ack, AckIdentity):
            return False
        if ack.command_id in self._expired:
            return False
        expected = self._pending.get(ack.command_id)
        if expected is None:
            return False
        exact = (
            ack.command_type == expected.command_type
            and ack.session_id == expected.session_id
            and ack.boot_id64 == expected.boot_id64
            and ack.stage_context_id == expected.stage_context_id
        )
        if not exact:
            return False
        del self._pending[ack.command_id]
        return True


def commit_intent_then_send(
    journal: DurableIntentJournal,
    identity: CommandIdentity,
    created_utc: str,
    send: Callable[[CommandIdentity], object],
) -> tuple[str, object]:
    """Durably record intent before invoking any transport send callback."""
    digest = journal.append_intent(identity, created_utc)
    result = send(identity)
    return digest, result
