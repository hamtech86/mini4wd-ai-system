"""3.0 V measured / 2.8 V projected motor-analysis values."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, slots=True)
class VoltageProjection:
    measured_voltage_v: float
    reference_voltage_v: float
    running_voltage_v: float
    reached_reference: bool
    measured_rpm: Optional[float]
    measured_current_a: Optional[float]
    measured_power_w: Optional[float]
    projected_rpm_2v8: Optional[float]
    projected_current_2v8: Optional[float]
    projected_power_2v8: Optional[float]
    projection_method: str


def project_linear(value: Optional[float], measured_v: float, target_v: float) -> Optional[float]:
    if value is None or measured_v <= 0:
        return None
    return float(value) * target_v / measured_v


def make_projection(
    measured_voltage_v: float,
    rpm: Optional[float],
    current_a: Optional[float],
    reference_v: float = 3.00,
    running_v: float = 2.80,
) -> VoltageProjection:
    power = None if current_a is None else measured_voltage_v * current_a
    return VoltageProjection(
        measured_voltage_v=measured_voltage_v,
        reference_voltage_v=reference_v,
        running_voltage_v=running_v,
        reached_reference=measured_voltage_v >= reference_v,
        measured_rpm=rpm,
        measured_current_a=current_a,
        measured_power_w=power,
        projected_rpm_2v8=project_linear(rpm, measured_voltage_v, running_v),
        projected_current_2v8=project_linear(current_a, measured_voltage_v, running_v),
        projected_power_2v8=(
            running_v * project_linear(current_a, measured_voltage_v, running_v)
            if current_a is not None and measured_voltage_v > 0
            else None
        ),
        projection_method="linear_first_order; projected_not_measured",
    )
