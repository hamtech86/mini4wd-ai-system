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


def _integer(value: object, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be int")


def _validate_window(w: Window) -> None:
    if not isinstance(w.channel, str) or not w.channel:
        raise ValueError("channel must be a non-empty string")
    _integer(w.boot_id64, "boot_id64")
    if not 0 <= w.boot_id64 <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError("boot_id64 must fit uint64")
    _integer(w.start_ns, "start_ns")
    _integer(w.end_ns, "end_ns")
    if w.start_ns >= w.end_ns:
        raise ValueError("window must be non-empty [start, end)")
    if w.expected is not None:
        # bool is an int subclass in Python, but it is never a valid sample count.
        # Classify it as an invalid value (ValueError), consistently with negatives.
        if isinstance(w.expected, bool):
            raise ValueError("expected must be a non-negative integer or None")
        _integer(w.expected, "expected")
        if w.expected < 0:
            raise ValueError("expected must be non-negative or None")


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
        if not isinstance(item, Observation):
            raise TypeError("observations must contain Observation values")
        if item.channel is None or item.boot_id64 is None or item.timestamp_ns is None:
            unattributable += 1
            continue
        if not isinstance(item.channel, str) or not item.channel:
            unattributable += 1
            continue
        try:
            _integer(item.boot_id64, "observation boot_id64")
            _integer(item.timestamp_ns, "timestamp_ns")
        except TypeError:
            unattributable += 1
            continue
        if not 0 <= item.boot_id64 <= 0xFFFFFFFFFFFFFFFF:
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


@dataclass(frozen=True)
class BatchLossSummary:
    """Window summaries plus one collection-wide unattributable count."""
    summaries: tuple[LossSummary, ...]
    unattributable: int


def summarize_many(
    windows: Iterable[Window], observations: Iterable[Observation]
) -> BatchLossSummary:
    """Attribute a collection once across non-overlapping windows.

    An observation with incomplete/invalid identity or timestamp is counted
    exactly once in the collection-wide unattributable field, never once per
    window. Fully identified observations outside all supplied windows are
    ignored. Overlapping windows for the same channel/epoch are rejected so
    one observation cannot be assigned to multiple summaries.
    """
    window_list = tuple(windows)
    items = tuple(observations)
    for window in window_list:
        _validate_window(window)
    for i, left in enumerate(window_list):
        for right in window_list[i + 1:]:
            if (left.channel, left.boot_id64) == (right.channel, right.boot_id64):
                if max(left.start_ns, right.start_ns) < min(left.end_ns, right.end_ns):
                    raise ValueError("overlapping windows for the same channel/epoch")

    assigned: list[list[Observation]] = [[] for _ in window_list]
    unattributable = 0
    for item in items:
        if not isinstance(item, Observation):
            raise TypeError("observations must contain Observation values")
        if (not isinstance(item.channel, str) or not item.channel
                or item.boot_id64 is None or item.timestamp_ns is None):
            unattributable += 1
            continue
        try:
            _integer(item.boot_id64, "observation boot_id64")
            _integer(item.timestamp_ns, "timestamp_ns")
        except TypeError:
            unattributable += 1
            continue
        if not 0 <= item.boot_id64 <= 0xFFFFFFFFFFFFFFFF:
            unattributable += 1
            continue
        matches = [
            index for index, window in enumerate(window_list)
            if (item.channel, item.boot_id64) == (window.channel, window.boot_id64)
            and window.start_ns <= item.timestamp_ns < window.end_ns
        ]
        if len(matches) > 1:
            raise ValueError("observation matches multiple windows")
        if matches:
            assigned[matches[0]].append(item)

    summaries = tuple(
        summarize(window, assigned[index])
        for index, window in enumerate(window_list)
    )
    return BatchLossSummary(summaries, unattributable)
