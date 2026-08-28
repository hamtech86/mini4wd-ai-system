"""Pure calculations for motor benchmark derived metrics.

This module intentionally has no UI/controller imports. It can be integrated into
the existing result screen without changing motor-drive behavior.
"""
from __future__ import annotations

from typing import Iterable, Mapping, Optional, Sequence, Tuple


NumberPair = Tuple[float, float]


def _number(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def valid_samples(samples: Iterable[object]) -> Sequence[NumberPair]:
    """Return (voltage, rpm) pairs with valid positive voltage."""
    rows = []
    for sample in samples or []:
        if isinstance(sample, Mapping):
            voltage = sample.get("motor_voltage", sample.get("voltage", sample.get("V")))
            rpm = sample.get("rpm", sample.get("RPM", sample.get("revolutions_per_minute")))
        else:
            voltage = getattr(sample, "motor_voltage", getattr(sample, "voltage", None))
            rpm = getattr(sample, "rpm", getattr(sample, "RPM", None))
        voltage = _number(voltage)
        rpm = _number(rpm)
        if voltage is not None and rpm is not None and voltage > 0:
            rows.append((voltage, rpm))
    return rows


def calculate(samples: Iterable[object]) -> dict:
    """Calculate average voltage/RPM and voltage-normalized RPM values.

    The normalization is explicitly a derived display metric; it must not be
    written back into the raw measurement samples.
    """
    rows = valid_samples(samples)
    if not rows:
        return {
            "sample_count": 0,
            "average_voltage": None,
            "average_rpm": None,
            "rpm_at_3v": None,
            "rpm_at_2_8v": None,
        }

    average_voltage = sum(v for v, _ in rows) / len(rows)
    average_rpm = sum(r for _, r in rows) / len(rows)
    return {
        "sample_count": len(rows),
        "average_voltage": average_voltage,
        "average_rpm": average_rpm,
        "rpm_at_3v": average_rpm * 3.0 / average_voltage,
        "rpm_at_2_8v": average_rpm * 2.8 / average_voltage,
    }
