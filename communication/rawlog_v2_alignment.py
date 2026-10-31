"""Timestamp-preserving alignment helpers for RawLog v2 AUX samples.

This module performs identity assignment, timestamp unwrapping and acquisition-
cycle grouping only. It does not calibrate ADC values or calculate resistance.
No maximum channel-skew threshold is imposed here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


_UINT32_MODULUS = 1 << 32
_UINT32_HALF_RANGE = 1 << 31


class AuxAlignmentError(ValueError):
    """Raised when AUX sample order/identity cannot be aligned safely."""


@dataclass(frozen=True)
class AlignedAuxSample:
    sample_id: str
    session_id: str
    sequence: int
    phase: str
    direction: str
    pwm: int
    run_state: str
    channel: str
    adc_raw: int
    timestamp_us: int
    timestamp_unwrapped_us: int


@dataclass(frozen=True)
class AuxAcquisitionCycle:
    session_id: str
    sequence: int
    phase: str
    direction: str
    pwm: int
    run_state: str
    samples: dict[str, AlignedAuxSample]
    metadata_consistent: bool
    metadata_error: str | None
    a4_a5_skew_us: int | None
    a4_a5_pair_valid: bool
    a4_a5_pair_reason: str | None


def _field(record, name):
    if isinstance(record, dict):
        return record[name]
    return getattr(record, name)


def align_aux_records(records: Iterable[object]) -> list[AuxAcquisitionCycle]:
    """Unwrap each session's micros() timeline and group samples by cycle.

    Input order is the serial acquisition order and is intentionally preserved.
    A backwards timestamp is treated as a wrap only when the backwards jump
    exceeds half the uint32 range; smaller backwards jumps are rejected.
    A4/A5 skew is reported as signed (A5 minus A4) microseconds. It is not
    compared with a policy threshold.
    """
    timelines = {}
    cycles = {}
    cycle_order = []

    for record in records:
        session_id = _field(record, "session_id")
        sequence = _field(record, "sequence")
        channel = _field(record, "channel")
        timestamp_us = _field(record, "timestamp_us")
        if not isinstance(session_id, str) or not session_id:
            raise AuxAlignmentError("session_id must be a non-empty string")
        if type(sequence) is not int or not 0 <= sequence < _UINT32_MODULUS:
            raise AuxAlignmentError("sequence must be uint32")
        if channel not in {"A0", "A1", "A4", "A5"}:
            raise AuxAlignmentError(f"unsupported channel: {channel!r}")
        if type(timestamp_us) is not int or not 0 <= timestamp_us < _UINT32_MODULUS:
            raise AuxAlignmentError("timestamp_us must be uint32")

        previous, offset = timelines.get(session_id, (None, 0))
        if previous is not None and timestamp_us < previous:
            backwards = previous - timestamp_us
            if backwards > _UINT32_HALF_RANGE:
                offset += _UINT32_MODULUS
            else:
                raise AuxAlignmentError(
                    f"timestamp moved backwards within session {session_id}: "
                    f"{previous} -> {timestamp_us}"
                )
        timelines[session_id] = (timestamp_us, offset)

        sample_id = f"{session_id}:{sequence}:{channel}"
        sample = AlignedAuxSample(
            sample_id=sample_id,
            session_id=session_id,
            sequence=sequence,
            phase=_field(record, "phase"),
            direction=_field(record, "direction"),
            pwm=_field(record, "pwm"),
            run_state=_field(record, "run_state"),
            channel=channel,
            adc_raw=_field(record, "adc_raw"),
            timestamp_us=timestamp_us,
            timestamp_unwrapped_us=offset + timestamp_us,
        )
        key = (session_id, sequence)
        if key not in cycles:
            cycles[key] = []
            cycle_order.append(key)
        cycles[key].append(sample)

    result = []
    for key in cycle_order:
        members = cycles[key]
        channels = {}
        for sample in members:
            if sample.channel in channels:
                raise AuxAlignmentError(
                    f"duplicate channel {sample.channel} in cycle {key}"
                )
            channels[sample.channel] = sample

        reference = members[0]
        consistent = all(
            (item.phase, item.direction, item.pwm, item.run_state)
            == (reference.phase, reference.direction, reference.pwm, reference.run_state)
            for item in members[1:]
        )
        metadata_error = None if consistent else "cycle metadata mismatch"
        a4 = channels.get("A4")
        a5 = channels.get("A5")
        if not consistent:
            pair_valid = False
            pair_reason = metadata_error
            skew = None
        elif a4 is None or a5 is None:
            pair_valid = False
            missing = "A4" if a4 is None else "A5"
            pair_reason = f"missing {missing} sample"
            skew = None
        else:
            pair_valid = True
            pair_reason = None
            skew = a5.timestamp_unwrapped_us - a4.timestamp_unwrapped_us

        result.append(AuxAcquisitionCycle(
            session_id=reference.session_id,
            sequence=reference.sequence,
            phase=reference.phase,
            direction=reference.direction,
            pwm=reference.pwm,
            run_state=reference.run_state,
            samples=channels,
            metadata_consistent=consistent,
            metadata_error=metadata_error,
            a4_a5_skew_us=skew,
            a4_a5_pair_valid=pair_valid,
            a4_a5_pair_reason=pair_reason,
        ))
    return result
