"""Aggregate a raw-log 3 V window without mutating the raw measurements."""
from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Iterable, Optional

from measurement.measurement import Measurement


@dataclass(frozen=True, slots=True)
class ThreeVoltSummary:
    reached_3v: bool
    sample_count: int
    max_motor_voltage_v: float
    mean_motor_voltage_v: Optional[float]
    mean_current_a: Optional[float]
    mean_rpm: Optional[float]
    mean_power_w: Optional[float]
    direction: Optional[str]


def _motor_voltage(m: Measurement) -> float:
    # A4 = voltage1, A5 = voltage2. Preserve direction in the raw value,
    # but use magnitude for performance evaluation.
    return abs(m.voltage1 - m.voltage2)


def summarize_3v_window(
    measurements: Iterable[Measurement],
    min_voltage_v: float = 3.00,
) -> ThreeVoltSummary:
    """Summarize only RUNNING samples at/above the 3 V reference.

    Samples below 3 V are not promoted to 3 V performance. If no qualifying
    sample exists, the maximum measured voltage is still reported so a
    magnetized motor that cannot reach 3 V remains diagnosable.
    """
    rows = [m for m in measurements if getattr(m, "state", "") == "RUNNING"]
    max_voltage = max((_motor_voltage(m) for m in rows), default=0.0)
    qualified = [m for m in rows if _motor_voltage(m) >= min_voltage_v]

    if not qualified:
        return ThreeVoltSummary(
            reached_3v=False,
            sample_count=0,
            max_motor_voltage_v=max_voltage,
            mean_motor_voltage_v=None,
            mean_current_a=None,
            mean_rpm=None,
            mean_power_w=None,
            direction=None,
        )

    currents = [float(m.current1) for m in qualified]
    powers = [float(m.electrical_power) for m in qualified]
    rpm_values = [getattr(m, "rpm", None) for m in qualified]
    rpm_values = [float(v) for v in rpm_values if v is not None]
    directions = {str(m.direction) for m in qualified if m.direction}

    return ThreeVoltSummary(
        reached_3v=True,
        sample_count=len(qualified),
        max_motor_voltage_v=max_voltage,
        mean_motor_voltage_v=mean(_motor_voltage(m) for m in qualified),
        mean_current_a=mean(currents),
        mean_rpm=mean(rpm_values) if rpm_values else None,
        mean_power_w=mean(powers),
        direction=next(iter(directions)) if len(directions) == 1 else "MIXED",
    )
