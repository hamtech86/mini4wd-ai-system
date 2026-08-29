"""Motor benchmark helpers.

The raw Measurement is never modified.  The benchmark uses the measured motor
terminal voltage as the source of truth and separates measured 3.00 V results
from the 2.80 V real-world estimate.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Iterable, Optional


TARGET_VOLTAGE = 3.00
REAL_WORLD_VOLTAGE = 2.80
VOLTAGE_TOLERANCE = 0.05


@dataclass(frozen=True, slots=True)
class MotorBenchmarkResult:
    measured_voltage: Optional[float]
    measured_rpm: Optional[float]
    measured_current: Optional[float]
    reached_3v: bool
    max_measured_voltage: Optional[float]
    estimated_rpm_2v8: Optional[float]
    estimated_current_2v8: Optional[float]
    voltage_scale: Optional[float]


def signed_motor_voltage(voltage1: float, voltage2: float) -> float:
    """Return signed terminal voltage: A4 (front) minus A5 (rear)."""
    return float(voltage1) - float(voltage2)


def motor_voltage(voltage1: float, voltage2: float) -> float:
    """Return terminal-voltage magnitude; direction is retained separately."""
    return abs(signed_motor_voltage(voltage1, voltage2))


def _finite(value: object) -> Optional[float]:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if isfinite(value) else None


def estimate_at_voltage(value_at_3v: Optional[float], target: float = REAL_WORLD_VOLTAGE) -> Optional[float]:
    """Scale a 3 V measured value for the 2.8 V reference.

    This is intentionally a first-order voltage-proportional estimate, not a
    claim of measured performance.  It is only valid when a genuine 3 V
    benchmark exists.
    """
    value = _finite(value_at_3v)
    if value is None:
        return None
    return value * float(target) / TARGET_VOLTAGE


def evaluate(samples: Iterable[object]) -> MotorBenchmarkResult:
    """Extract a 3 V benchmark and a clearly-labelled 2.8 V estimate.

    Samples before stable operation are expected to have been excluded by the
    benchmark controller.  No synthetic 3 V value is created when the motor
    never reaches 3 V.
    """
    rows = list(samples)
    valid = []
    for row in rows:
        voltage = _finite(getattr(row, "motor_voltage", None))
        if voltage is None:
            continue
        rpm = _finite(getattr(row, "rpm", None))
        current = _finite(getattr(row, "current1", None))
        valid.append((voltage, rpm, current))

    if not valid:
        return MotorBenchmarkResult(None, None, None, False, None, None, None, None)

    max_voltage = max(v for v, _, _ in valid)
    at_3v = [r for r in valid if abs(r[0] - TARGET_VOLTAGE) <= VOLTAGE_TOLERANCE]
    if not at_3v:
        return MotorBenchmarkResult(
            None, None, None, False, max_voltage, None, None, None
        )

    # Prefer the sample closest to exactly 3.00 V.
    measured = min(at_3v, key=lambda r: abs(r[0] - TARGET_VOLTAGE))
    voltage, rpm, current = measured
    scale = REAL_WORLD_VOLTAGE / TARGET_VOLTAGE
    return MotorBenchmarkResult(
        voltage,
        rpm,
        current,
        True,
        max_voltage,
        estimate_at_voltage(rpm),
        estimate_at_voltage(current),
        scale,
    )
