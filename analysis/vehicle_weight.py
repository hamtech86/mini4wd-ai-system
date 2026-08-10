"""Vehicle weight estimation for the 3 V motor benchmark.

This module intentionally provides a *benchmark estimate*, not a physical
vehicle-dynamics calculation.  The initial calibration is anchored to the
system's existing 130 g benchmark vehicle and 0.83 g·cm measured torque.
The calibration is configurable so real track data can replace it later.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VehicleWeightEstimate:
    center_g: float
    minimum_g: float
    maximum_g: float
    tire_diameter_mm: float
    gear_ratio: float
    confidence: float
    basis: str


def estimate_vehicle_weight(
    torque_gcm: float,
    *,
    reference_torque_gcm: float = 0.83,
    reference_weight_g: float = 130.0,
    lower_factor: float = 0.75,
    upper_factor: float = 1.25,
    tire_diameter_mm: float = 24.0,
    gear_ratio: float = 3.5,
    confidence: float = 0.40,
) -> VehicleWeightEstimate:
    """Return a provisional compatible-weight range from measured torque.

    The 24 mm tire / 3.5:1 gearing is part of the benchmark definition.
    Weight is scaled linearly from the benchmark reference.  This is a
    comparison index until enough real-machine data exists to calibrate the
    model against measured acceleration/lap performance.
    """
    torque = max(0.0, float(torque_gcm))
    reference_torque = max(1e-9, float(reference_torque_gcm))
    reference_weight = max(0.0, float(reference_weight_g))

    center = reference_weight * torque / reference_torque
    minimum = center * max(0.0, float(lower_factor))
    maximum = center * max(float(lower_factor), float(upper_factor))

    return VehicleWeightEstimate(
        center_g=center,
        minimum_g=minimum,
        maximum_g=maximum,
        tire_diameter_mm=float(tire_diameter_mm),
        gear_ratio=float(gear_ratio),
        confidence=float(confidence),
        basis="Provisional benchmark calibration; course/roller/brake/grip factors excluded",
    )
