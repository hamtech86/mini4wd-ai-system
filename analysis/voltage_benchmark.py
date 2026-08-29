"""Motor voltage benchmark and 2.8 V projection.

Raw Measurement data is never modified. 3.00 V is the reference
benchmark; 2.80 V is a projected running-voltage point.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from measurement.measurement import Measurement


@dataclass(frozen=True, slots=True)
class VoltageBenchmark:
    reference_voltage: float = 3.00
    running_voltage: float = 2.80
    measured_voltage: float = 0.0
    reached_reference: bool = False
    rpm: Optional[float] = None
    current: Optional[float] = None
    power: Optional[float] = None
    projected_rpm_2v8: Optional[float] = None
    projected_current_2v8: Optional[float] = None
    projected_power_2v8: Optional[float] = None


def motor_voltage_signed(measurement: Measurement) -> float:
    """Return signed A4-A5 voltage; direction is therefore preserved."""
    return measurement.voltage1 - measurement.voltage2


def motor_voltage_abs(measurement: Measurement) -> float:
    """Return magnitude of voltage across the motor."""
    return abs(motor_voltage_signed(measurement))


def project_to_2v8(
    measured_voltage: float,
    value: float,
    target_voltage: float = 2.80,
) -> float:
    """Simple first-order voltage projection.

    This is explicitly a projection, not a measurement. It must not be used
    when the measured voltage is zero or when a non-linear motor model is
    available. Keeping this function isolated allows later calibration.
    """
    if measured_voltage <= 0:
        raise ValueError("measured_voltage must be > 0")
    return value * target_voltage / measured_voltage


def benchmark_measurement(
    measurement: Measurement,
    rpm: Optional[float] = None,
    current: Optional[float] = None,
) -> VoltageBenchmark:
    """Create a benchmark record without altering the source Measurement.

    A sample below 3.00 V is never labelled as a 3 V measurement. This is
    particularly important for magnetized motors that may fail to reach 3 V.
    """
    voltage = motor_voltage_abs(measurement)
    reached = voltage >= 3.00

    power = None
    rpm_28 = None
    current_28 = None
    power_28 = None

    if current is not None:
        power = voltage * current
        current_28 = project_to_2v8(voltage, current)
        power_28 = 2.80 * current_28
    if rpm is not None:
        rpm_28 = project_to_2v8(voltage, rpm)

    return VoltageBenchmark(
        measured_voltage=voltage,
        reached_reference=reached,
        rpm=rpm,
        current=current,
        power=power,
        projected_rpm_2v8=rpm_28,
        projected_current_2v8=current_28,
        projected_power_2v8=power_28,
    )
