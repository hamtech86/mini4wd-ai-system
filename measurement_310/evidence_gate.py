"""Fail-closed host evidence gate for 310-5 T05.

This is an injectable host-side policy harness. It does not claim that STOP
reaches the MCU or that filesystem fsync models physical power loss.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from .command_intent import (
    AckCorrelator,
    AckIdentity,
    CommandIdentity,
    DurableIntentJournal,
    IntentError,
)


class EvidenceGateError(RuntimeError):
    pass


@dataclass(frozen=True)
class SendOutcome:
    sent: bool
    stopped_attempted: bool
    reason: Optional[str] = None


class EvidenceGate:
    """Prevent nonzero sends unless intent/evidence persistence succeeds."""

    def __init__(
        self,
        journal: DurableIntentJournal,
        send_payload: Callable[[CommandIdentity, bytes], object],
        send_stop: Callable[[], object],
        append_evidence: Callable[[dict], object],
        correlator: Optional[AckCorrelator] = None,
    ):
        self.journal = journal
        self.send_payload = send_payload
        self.send_stop = send_stop
        self.append_evidence = append_evidence
        self.correlator = correlator or AckCorrelator()
        self.failed = False
        self.failure_reason: Optional[str] = None

    def _fail_and_stop(self, reason: str) -> SendOutcome:
        self.failed = True
        self.failure_reason = reason
        attempted = False
        try:
            self.send_stop()
            attempted = True
        except Exception:
            attempted = True  # attempted; delivery/result remains unknown
        return SendOutcome(False, attempted, reason)

    def send(self, identity: CommandIdentity, payload: bytes, created_utc: str) -> SendOutcome:
        if self.failed:
            return SendOutcome(False, False, self.failure_reason or "evidence gate is latched")
        if not isinstance(payload, bytes):
            raise TypeError("payload must be immutable bytes")
        if identity.command_type == "PWM" and payload and payload != b"\x00":
            # This generic harness treats any nonzero payload as potentially energizing.
            # Production integration must provide a protocol-aware zero/nonzero predicate.
            potentially_nonzero = True
        else:
            potentially_nonzero = False
        try:
            self.journal.append_intent(identity, created_utc)
            self.correlator.register(identity)
        except Exception as exc:
            return self._fail_and_stop(f"durable intent failed: {exc}")
        if self.failed:
            return SendOutcome(False, False, self.failure_reason)
        try:
            self.send_payload(identity, payload)
            return SendOutcome(True, False)
        except Exception as exc:
            self.failed = True
            self.failure_reason = f"transport send outcome uncertain: {exc}"
            return SendOutcome(False, False, self.failure_reason)

    def record_evidence(self, record: dict) -> bool:
        if self.failed:
            return False
        try:
            self.append_evidence(record)
            return True
        except Exception as exc:
            self._fail_and_stop(f"evidence append failed: {exc}")
            return False

    def accept_ack(self, ack: AckIdentity, evidence_record: dict) -> bool:
        if self.failed:
            return False
        if not self.correlator.correlate(ack):
            return False
        # Correlation alone does not advance a stage; ACK evidence must also persist.
        return self.record_evidence(evidence_record)

    def expire(self, command_id: str) -> None:
        self.correlator.expire(command_id)
