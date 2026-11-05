"""Host-side uint16 device-sequence accounting for 310 safety tests.

The tracker is deliberately scoped to one *full* boot epoch. Callers must create
a new tracker only after establishing that the complete boot_id64 changed.
This module does not write or alter RawLog records.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


UINT16_MODULUS = 1 << 16
UINT16_MASK = UINT16_MODULUS - 1
MAX_UNAMBIGUOUS_FORWARD_DELTA = (UINT16_MODULUS // 2) - 1


class SequenceDisposition(str, Enum):
    FIRST = "first"
    NEXT = "next"
    WRAP = "wrap"
    GAP = "gap"
    DUPLICATE = "duplicate"
    CONFLICTING_DUPLICATE = "conflicting_duplicate"
    UNVERIFIED_REPLAY = "unverified_replay"
    AMBIGUOUS_DELTA = "ambiguous_delta"
    STALE_OR_BACKWARD = "stale_or_backward"


@dataclass(frozen=True)
class SequenceResult:
    disposition: SequenceDisposition
    wire_sequence: int
    extended_sequence: Optional[int]
    forward_delta: Optional[int]
    missing_count: int = 0
    accepted: bool = False
    detail: str = ""


class DeviceSequenceTracker:
    """Extend uint16 sequence numbers within a caller-verified boot epoch.

    Only forward deltas in [1, 32767] advance the extended sequence. A delta
    of 32768 is mathematically ambiguous. Deltas in [32769, 65535] are treated
    as stale/backward and never rebase the counter. An exact same-sequence,
    same-payload frame is deduplicated; a different payload is a conflict.

    Payload equality is byte-for-byte. The caller should pass the canonical
    decoded frame payload (not a mutable object).
    """

    def __init__(self, boot_id64: int):
        if isinstance(boot_id64, bool) or not isinstance(boot_id64, int):
            raise TypeError("boot_id64 must be an integer")
        if not 0 <= boot_id64 <= 0xFFFFFFFFFFFFFFFF:
            raise ValueError("boot_id64 must fit uint64")
        self.boot_id64 = boot_id64
        self._last_wire: Optional[int] = None
        self._last_payload: Optional[bytes] = None
        self._extended: Optional[int] = None

    @classmethod
    def from_checkpoint(cls, boot_id64: int, extended_sequence: int,
                        wire_sequence: int) -> "DeviceSequenceTracker":
        """Restore sequence position without inventing the previous payload.

        Since the checkpoint does not persist the prior frame bytes, a frame
        repeating the checkpoint's wire sequence cannot be proven an exact
        duplicate after process restart and is classified UNVERIFIED_REPLAY.
        """
        tracker = cls(boot_id64)
        if isinstance(extended_sequence, bool) or not isinstance(extended_sequence, int):
            raise TypeError("extended_sequence must be an integer")
        if extended_sequence < 0:
            raise ValueError("extended_sequence cannot be negative")
        if isinstance(wire_sequence, bool) or not isinstance(wire_sequence, int):
            raise TypeError("wire_sequence must be an integer")
        if not 0 <= wire_sequence <= UINT16_MASK:
            raise ValueError("wire_sequence must fit uint16")
        if (extended_sequence & UINT16_MASK) != wire_sequence:
            raise ValueError("wire_sequence must match extended_sequence low bits")
        tracker._last_wire = wire_sequence
        tracker._extended = extended_sequence
        tracker._last_payload = None
        return tracker

    @property
    def last_extended_sequence(self) -> Optional[int]:
        return self._extended

    @property
    def last_wire_sequence(self) -> Optional[int]:
        return self._last_wire

    def observe(self, wire_sequence: int, payload: bytes) -> SequenceResult:
        if isinstance(wire_sequence, bool) or not isinstance(wire_sequence, int):
            raise TypeError("wire_sequence must be an integer")
        if not 0 <= wire_sequence <= UINT16_MASK:
            raise ValueError("wire_sequence must fit uint16")
        if not isinstance(payload, bytes):
            raise TypeError("payload must be immutable bytes")

        if self._last_wire is None:
            self._last_wire = wire_sequence
            self._last_payload = payload
            self._extended = wire_sequence
            return SequenceResult(
                SequenceDisposition.FIRST, wire_sequence, self._extended, None,
                accepted=True, detail="initial sequence in verified boot epoch",
            )

        assert self._extended is not None
        delta = (wire_sequence - self._last_wire) & UINT16_MASK

        if delta == 0:
            if self._last_payload is None:
                return SequenceResult(
                    SequenceDisposition.UNVERIFIED_REPLAY, wire_sequence,
                    self._extended, 0, accepted=False,
                    detail="same sequence as checkpoint; prior payload unavailable after restart",
                )
            if payload == self._last_payload:
                return SequenceResult(
                    SequenceDisposition.DUPLICATE, wire_sequence,
                    self._extended, 0, accepted=False,
                    detail="exact duplicate; no new sample is emitted",
                )
            return SequenceResult(
                SequenceDisposition.CONFLICTING_DUPLICATE, wire_sequence,
                self._extended, 0, accepted=False,
                detail="same wire sequence carries different payload",
            )

        if delta == UINT16_MODULUS // 2:
            return SequenceResult(
                SequenceDisposition.AMBIGUOUS_DELTA, wire_sequence,
                None, delta, accepted=False,
                detail="half-range delta cannot establish ordering",
            )

        if delta > UINT16_MODULUS // 2:
            return SequenceResult(
                SequenceDisposition.STALE_OR_BACKWARD, wire_sequence,
                None, delta, accepted=False,
                detail="backward/stale frame; tracker is not rebased",
            )

        next_extended = self._extended + delta
        missing = delta - 1
        disposition = (
            SequenceDisposition.WRAP
            if wire_sequence < self._last_wire
            else SequenceDisposition.GAP
            if missing
            else SequenceDisposition.NEXT
        )
        self._last_wire = wire_sequence
        self._last_payload = payload
        self._extended = next_extended
        return SequenceResult(
            disposition, wire_sequence, next_extended, delta,
            missing_count=missing, accepted=True,
            detail="forward frame accepted; gaps are accounted, not synthesized",
        )
