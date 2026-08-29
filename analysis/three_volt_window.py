"""Extract the 3 V evaluation window from raw motor measurements.

The raw Measurement objects remain untouched.  This module only derives an
analysis view from them, so the same logs can be re-analysed when the model
changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from measurement.measurement import Measurement


@dataclass(frozen=True, slots=True)
class ThreeVoltWindow:
    samples: tuple[Measurement, ...]
    max_motor_voltage: float
    reached_3v: bool
    max_voltage_sample: Optional[Measurement]
    reason: str


def signed_motor_voltage(sample: Measurement) -> float:
    """A4(front) - A5(rear), preserving rotation polarity."""
    return sample.voltage1 - sample.voltage2


def motor_voltage(sample: Measurement) -> float:
    """Magnitude of voltage actually applied across the motor."""
    return abs(signed_motor_voltage(sample))


def _is_stable_running(sample: Measurement) -> bool:
    # PWM>0 alone is insufficient for magnetized motors: keep explicit RUNNING
    # states when firmware supplies them, while remaining compatible with
    # older logs whose state field may be empty.
    state = (sample.state or "").strip().upper()
    if state in {"START", "STARTING", "STOP", "STOPPED", "IDLE", "ASSIST"}:
        return False
    return state == "RUNNING" or (not state and sample.pwm > 0)


def extract_3v_window(
    samples: Iterable[Measurement],
    reference_voltage: float = 3.00,
) -> ThreeVoltWindow:
    """Return only valid running samples at/above the 3 V benchmark.

    A motor that never reaches 3 V is explicitly marked as not reaching the
    benchmark. Its highest measured running voltage is retained for diagnosis,
    but it is never relabelled as a 3 V measurement.
    """
    running = tuple(s for s in samples if _is_stable_running(s))
    if not running:
        return ThreeVoltWindow((), 0.0, False, None, "NO_STABLE_RUNNING_SAMPLE")

    voltages = tuple(motor_voltage(s) for s in running)
    max_voltage = max(voltages)
    max_index = voltages.index(max_voltage)
    max_sample = running[max_index]

    valid = tuple(
        s for s in running if motor_voltage(s) >= reference_voltage
    )
    if not valid:
        return ThreeVoltWindow(
            (), max_voltage, False, max_sample, "REFERENCE_3V_NOT_REACHED"
        )

    return ThreeVoltWindow(
        valid,
        max_voltage,
        True,
        max_sample,
        "3V_REFERENCE_REACHED",
    )
