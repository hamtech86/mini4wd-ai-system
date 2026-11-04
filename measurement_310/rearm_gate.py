"""310-5 R01: separate RawLog recovery from actuation re-arm authorization.

Host-side evidence only. This module does not alter RawLog v2 or firmware and
cannot prove electrical cutoff, rotor stop, or target-storage durability.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
from enum import Enum
import fcntl
import hashlib
import json
import os
from pathlib import Path
from typing import Callable, Optional


class RearmGateError(RuntimeError):
    pass


class JournalUntrusted(RearmGateError):
    pass


class WriteFlushStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class CommandIdentity:
    command_id: str
    command_type: str
    session_id: str
    boot_id64: int
    stage_context_id: str

    def __post_init__(self):
        for key in ("command_id", "command_type", "session_id", "stage_context_id"):
            value = getattr(self, key)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{key} must be a non-empty string")
        if isinstance(self.boot_id64, bool) or not isinstance(self.boot_id64, int) or not 0 <= self.boot_id64 <= 0xFFFFFFFFFFFFFFFF:
            raise ValueError("boot_id64 must be uint64")


@dataclass(frozen=True)
class AckIdentity:
    command_id: str
    command_type: str
    session_id: str
    boot_id64: int
    stage_context_id: str

    def matches(self, identity: CommandIdentity) -> bool:
        return asdict(self) == asdict(identity)


@dataclass(frozen=True)
class CommandState:
    identity: CommandIdentity
    write_flush: Optional[WriteFlushStatus] = None
    ack_matched: bool = False
    terminal_safe: bool = False


@dataclass(frozen=True)
class RearmDecision:
    allowed: bool
    reason: str


class ActuationSafetyJournal:
    """Append-only, hash-chained command lifecycle journal; no replay API."""

    FORMAT = "310-r01-actuation-journal-v1"

    def __init__(self, path):
        self.path = Path(path)

    @staticmethod
    def _canonical(value):
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()

    def _read(self):
        if not self.path.exists():
            return []
        raw = self.path.read_bytes()
        if raw and not raw.endswith(b"\n"):
            raise JournalUntrusted("torn journal tail")
        previous, bodies = "0" * 64, []
        for number, line in enumerate(raw.splitlines(), 1):
            try:
                envelope = json.loads(line.decode())
                body = envelope["body"]
                digest = hashlib.sha256(self._canonical(body)).hexdigest()
                if envelope["sha256"] != digest or body["previous_hash"] != previous:
                    raise ValueError("hash chain mismatch")
                if body.get("format") != self.FORMAT:
                    raise ValueError("unsupported journal format")
                previous = digest
                bodies.append(body)
            except (ValueError, KeyError, TypeError, UnicodeError) as exc:
                raise JournalUntrusted(f"invalid record {number}: {exc}") from exc
        return bodies

    def _append(self, event, payload):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lock = os.open(str(self.path) + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(lock, fcntl.LOCK_EX)
            bodies = self._read()
            previous = hashlib.sha256(self._canonical(bodies[-1])).hexdigest() if bodies else "0" * 64
            body = {"format": self.FORMAT, "event": event, "payload": payload, "previous_hash": previous}
            line = self._canonical({"body": body, "sha256": hashlib.sha256(self._canonical(body)).hexdigest()}) + b"\n"
            fd = os.open(str(self.path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                if os.write(fd, line) != len(line):
                    raise RearmGateError("short journal append; command outcome uncertain")
                os.fsync(fd)
                dfd = os.open(str(self.path.parent), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
                try:
                    os.fsync(dfd)
                finally:
                    os.close(dfd)
            except OSError as exc:
                raise RearmGateError(f"journal durability uncertain: {exc}") from exc
            finally:
                os.close(fd)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
            os.close(lock)

    def recover(self):
        states = {}
        for body in self._read():
            event, p = body["event"], body["payload"]
            try:
                identity = CommandIdentity(**p["identity"])
                cid = identity.command_id
                old = states.get(cid)
                if event == "INTENT":
                    if old is not None:
                        raise ValueError("duplicate intent")
                    states[cid] = CommandState(identity)
                elif old is None or old.identity != identity:
                    raise ValueError("event without matching intent")
                elif event == "WRITE_FLUSH":
                    if old.write_flush is not None or old.terminal_safe:
                        raise ValueError("duplicate/late write result")
                    states[cid] = CommandState(identity, WriteFlushStatus(p["status"]))
                elif event == "ACK_MATCHED":
                    ack = AckIdentity(**p["ack"])
                    if old.write_flush is not WriteFlushStatus.SUCCEEDED or old.ack_matched or not ack.matches(identity):
                        raise ValueError("invalid ACK transition")
                    states[cid] = CommandState(identity, old.write_flush, True, False)
                elif event == "TERMINAL_SAFE":
                    if old.terminal_safe or p.get("device_safe_state_confirmed") is not True:
                        raise ValueError("invalid terminal state")
                    if not isinstance(p.get("operator_decision_id"), str) or not p["operator_decision_id"].strip():
                        raise ValueError("missing operator decision")
                    expected = "ACK_AND_OPERATOR_CONFIRMATION" if old.ack_matched else "OPERATOR_RECONCILIATION"
                    if p.get("source") != expected:
                        raise ValueError("terminal source/evidence mismatch")
                    states[cid] = CommandState(identity, old.write_flush, old.ack_matched, True)
                else:
                    raise ValueError(f"unknown event {event}")
            except (KeyError, TypeError, ValueError) as exc:
                raise JournalUntrusted(f"invalid lifecycle transition: {exc}") from exc
        return states

    def record_intent(self, identity):
        if identity.command_id in self.recover():
            raise RearmGateError("command_id reuse prohibited")
        self._append("INTENT", {"identity": asdict(identity)})

    def record_write_flush(self, identity, status):
        if not isinstance(status, WriteFlushStatus):
            raise TypeError("status must be WriteFlushStatus")
        state = self.recover().get(identity.command_id)
        if state is None or state.identity != identity or state.write_flush is not None:
            raise RearmGateError("write/flush result lacks unique intent")
        self._append("WRITE_FLUSH", {"identity": asdict(identity), "status": status.value})

    def record_ack(self, identity, ack):
        state = self.recover().get(identity.command_id)
        if state is None or state.identity != identity or state.write_flush is not WriteFlushStatus.SUCCEEDED or state.ack_matched:
            return False
        if not isinstance(ack, AckIdentity) or not ack.matches(identity):
            return False
        self._append("ACK_MATCHED", {"identity": asdict(identity), "ack": asdict(ack)})
        return True

    def record_terminal_safe(self, identity, *, operator_decision_id, device_safe_state_confirmed):
        if not isinstance(operator_decision_id, str) or not operator_decision_id.strip():
            raise ValueError("explicit operator_decision_id required")
        if device_safe_state_confirmed is not True:
            raise ValueError("device safe state must be explicitly confirmed")
        state = self.recover().get(identity.command_id)
        if state is None or state.identity != identity or state.terminal_safe:
            raise RearmGateError("terminal state lacks unique unresolved command")
        source = "ACK_AND_OPERATOR_CONFIRMATION" if state.ack_matched else "OPERATOR_RECONCILIATION"
        self._append("TERMINAL_SAFE", {
            "identity": asdict(identity), "operator_decision_id": operator_decision_id,
            "device_safe_state_confirmed": True, "source": source,
        })


class ActuationRearmGate:
    """Both storage recovery and independent device-state reconciliation are required."""

    def __init__(self, journal):
        self.journal = journal

    def evaluate(self, *, rawlog_recovery_succeeded, operator_decision_id, device_safe_state_confirmed):
        if rawlog_recovery_succeeded is not True:
            return RearmDecision(False, "RawLog package recovery incomplete/failed")
        if not isinstance(operator_decision_id, str) or not operator_decision_id.strip():
            return RearmDecision(False, "explicit operator decision required")
        if device_safe_state_confirmed is not True:
            return RearmDecision(False, "device safe state not independently confirmed")
        try:
            states = self.journal.recover()
        except JournalUntrusted as exc:
            return RearmDecision(False, f"actuation journal untrusted: {exc}")
        unresolved = sorted(cid for cid, state in states.items() if not state.terminal_safe)
        if unresolved:
            return RearmDecision(False, "unresolved command outcome(s): " + ", ".join(unresolved))
        return RearmDecision(True, "both independent gates satisfied")

    def arm_if_allowed(self, *, rawlog_recovery_succeeded, operator_decision_id,
                       device_safe_state_confirmed, send_nonzero: Callable[[], object]):
        decision = self.evaluate(
            rawlog_recovery_succeeded=rawlog_recovery_succeeded,
            operator_decision_id=operator_decision_id,
            device_safe_state_confirmed=device_safe_state_confirmed,
        )
        return (decision, send_nonzero()) if decision.allowed else (decision, None)
