"""Deterministic host-side, epoch-local loss accounting (candidate T11).

This module does not modify RawLog and cannot prove device-side acquisition.
Callers must provide already-attributed observations and a known expected count
when one exists. Windows are half-open: start <= timestamp < end.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Iterable, Optional


@dataclass(frozen=True)
class Window:
    channel: str
    boot_id64: int
    start_ns: int
    end_ns: int
    expected: Optional[int]


@dataclass(frozen=True)
class Observation:
    channel: Optional[str]
    boot_id64: Optional[int]
    timestamp_ns: Optional[int]
    disposition: str
    # disposition: valid, invalid, duplicate, conflicting_duplicate


@dataclass(frozen=True)
class LossSummary:
    channel: str
    boot_id64: int
    start_ns: int
    end_ns: int
    expected: Optional[int]
    attempts: int
    valid: int
    invalid: int
    duplicates: int
    conflicts: int
    missing: Optional[int]
    excess: int
    unattributable: int
    digest_sha256: str


def _validate_window(w: Window) -> None:
    if not w.channel:
        raise ValueError("channel must be non-empty")
    if isinstance(w.boot_id64, bool) or not isinstance(w.boot_id64, int):
        raise TypeError("boot_id64 must be int")
    if not 0 <= w.boot_id64 <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError("boot_id64 must fit uint64")
    if w.start_ns >= w.end_ns:
        raise ValueError("window must be non-empty [start, end)")
    if w.expected is not None and (isinstance(w.expected, bool) or w.expected < 0):
        raise ValueError("expected must be a non-negative integer or None")


def summarize(window: Window, observations: Iterable[Observation]) -> LossSummary:
    """Summarize observations deterministically for one channel/epoch/window.

    Only valid and invalid observations count as attempts within the window.
    Duplicates/conflicts are separately counted and never inflate sample counts.
    Missing stays None if expected is unknown. Unassigned observations increment
    unattributable; observations attributed elsewhere are simply outside scope.
    """
    _validate_window(window)
    valid = invalid = duplicates = conflicts = attempts = unattributable = 0

    for item in observations:
        if item.channel is None or item.boot_id64 is None or item.timestamp_ns is None:
            unattributable += 1
            continue
        if (item.channel, item.boot_id64) != (window.channel, window.boot_id64):
            continue
        if not window.start_ns <= item.timestamp_ns < window.end_ns:
            continue

        if item.disposition == "valid":
            valid += 1
            attempts += 1
        elif item.disposition == "invalid":
            invalid += 1
            attempts += 1
        elif item.disposition == "duplicate":
            duplicates += 1
        elif item.disposition == "conflicting_duplicate":
            conflicts += 1
        else:
            raise ValueError(f"unknown disposition: {item.disposition!r}")

    accounted = valid + invalid
    missing = None if window.expected is None else max(0, window.expected - accounted)
    excess = 0 if window.expected is None else max(0, accounted - window.expected)
    canonical = {
        "channel": window.channel,
        "boot_id64": window.boot_id64,
        "start_ns": window.start_ns,
        "end_ns": window.end_ns,
        "expected": window.expected,
        "attempts": attempts,
        "valid": valid,
        "invalid": invalid,
        "duplicates": duplicates,
        "conflicts": conflicts,
        "missing": missing,
        "excess": excess,
        "unattributable": unattributable,
    }
    digest = sha256(json.dumps(canonical, sort_keys=True, separators=(",", ":"),
                              ensure_ascii=True).encode("utf-8")).hexdigest()
    return LossSummary(**canonical, digest_sha256=digest)


def canonical_json(summary: LossSummary) -> str:
    """Stable serialization suitable for deterministic host fixtures."""
    return json.dumps(asdict(summary), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)
