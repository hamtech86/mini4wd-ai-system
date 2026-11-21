"""Strict parser for additive RawLog v2 AUX telemetry records.

AUX records carry raw ADC counts and per-conversion Arduino micros() timestamps.
This module intentionally performs no calibration, pairing, or measurement math.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Final


_UINT32_MAX: Final = (1 << 32) - 1
_TOKEN_RE: Final = re.compile(r"^[A-Za-z0-9_.-]+$")
_CHANNELS: Final = frozenset({"A0", "A1", "A4", "A5"})
_DIRECTIONS: Final = frozenset({"FWD", "REV", "STOP"})


@dataclass(frozen=True)
class AuxRecord:
    protocol_version: int
    session_id: str
    sequence: int
    phase: str
    direction: str
    pwm: int
    run_state: str
    channel: str
    adc_raw: int
    timestamp_us: int
    raw_line: str


class AuxParseError(ValueError):
    """Raised when an AUX wire record violates the v2 contract."""


def _uint(value: str, field: str, maximum: int) -> int:
    if not value or not value.isascii() or not value.isdecimal():
        raise AuxParseError(f"{field} must be an unsigned decimal integer")
    number = int(value, 10)
    if number > maximum:
        raise AuxParseError(f"{field} out of range: {number}")
    return number


def _token(value: str, field: str) -> str:
    if not value or not _TOKEN_RE.fullmatch(value):
        raise AuxParseError(f"{field} must be a non-empty ASCII token")
    return value


def parse_aux_line(line: str) -> AuxRecord:
    """Parse one AUX v2 record, preserving its exact content sans terminator."""
    if not isinstance(line, str):
        raise AuxParseError("line must be str")
    raw = line.rstrip("\r\n")
    if not raw:
        raise AuxParseError("empty AUX record")
    fields = raw.split(",")
    if len(fields) != 11:
        raise AuxParseError(f"AUX v2 requires exactly 11 fields, got {len(fields)}")
    if fields[0] != "AUX":
        raise AuxParseError("record_type must be AUX")
    version = _uint(fields[1], "protocol_version", 255)
    if version != 2:
        raise AuxParseError(f"unsupported AUX protocol version: {version}")

    session_id = _token(fields[2], "session_id")
    sequence = _uint(fields[3], "sequence", _UINT32_MAX)
    phase = _token(fields[4], "phase")
    direction = fields[5]
    if direction not in _DIRECTIONS:
        raise AuxParseError(f"invalid direction: {direction!r}")
    pwm = _uint(fields[6], "pwm", 255)
    run_state = _token(fields[7], "run_state")
    channel = fields[8]
    if channel not in _CHANNELS:
        raise AuxParseError(f"invalid channel: {channel!r}")
    adc_raw = _uint(fields[9], "adc_raw", 1023)
    timestamp_us = _uint(fields[10], "timestamp_us", _UINT32_MAX)

    return AuxRecord(
        protocol_version=version,
        session_id=session_id,
        sequence=sequence,
        phase=phase,
        direction=direction,
        pwm=pwm,
        run_state=run_state,
        channel=channel,
        adc_raw=adc_raw,
        timestamp_us=timestamp_us,
        raw_line=raw,
    )
