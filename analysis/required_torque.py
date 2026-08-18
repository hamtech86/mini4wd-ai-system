"""Vehicle requirement -> motor torque conversion.

The model is intentionally physics-based and configurable.  It accepts the
same parameters the simulator is designed around: vehicle mass, tyre diameter,
gear ratio, tyre/course friction, and grade angle/length.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

from analysis.models import EstimatedValue, RequiredTorqueResult


G = 9.80665
NM_TO_GCM = 10197.1621298  # 1 N·m = 101.9716213 kgf·cm = 10197.16 g·cm


@dataclass(frozen=True)
class VehicleSpec:
    weight_g: float
    tire_diameter_mm: float = 24.0
    gear_ratio: float = 3.5
    tire_course_mu: float = 0.90
    rolling_resistance: float = 0.02
    grade_angle_deg: float = 0.0
    grade_length_mm: float = 0.0
    acceleration_mps2: float = 0.0
    drivetrain_efficiency: float = 0.85
    traction_margin: float = 0.90


class RequiredTorqueAnalysis:
    """Calculate minimum motor torque for a vehicle/course condition."""

    def calculate(self, spec: VehicleSpec | Mapping[str, float]) -> RequiredTorqueResult:
        if not isinstance(spec, VehicleSpec):
            spec = VehicleSpec(**dict(spec))

        mass = max(0.0, spec.weight_g) / 1000.0
        radius_m = max(0.1, spec.tire_diameter_mm) / 2000.0
        ratio = max(0.01, spec.gear_ratio)
        efficiency = max(0.05, min(1.0, spec.drivetrain_efficiency))
        angle = math.radians(spec.grade_angle_deg)

        rolling = mass * G * max(0.0, spec.rolling_resistance) * math.cos(angle)
        grade = mass * G * math.sin(angle)
        acceleration = mass * max(0.0, spec.acceleration_mps2)
        wheel_force = max(0.0, rolling + grade + acceleration)

        # Motor torque required at the shaft.
        required_nm = wheel_force * radius_m / (ratio * efficiency)
        required_gcm = required_nm * NM_TO_GCM

        # Maximum force before tyre/course slip.  The margin deliberately leaves
        # room for real-world variation rather than using the theoretical limit.
        traction_limit = max(0.0, spec.tire_course_mu) * mass * G * max(0.0, spec.traction_margin)
        usable_force = min(wheel_force, traction_limit) if traction_limit > 0 else wheel_force
        usable_nm = usable_force * radius_m / (ratio * efficiency)
        usable_gcm = usable_nm * NM_TO_GCM
        traction_limited = wheel_force > traction_limit > 0

        return RequiredTorqueResult(
            required_torque_gcm=EstimatedValue(required_gcm, "g·cm", 0.80),
            usable_traction_torque_gcm=EstimatedValue(usable_gcm, "g·cm", 0.70),
            traction_limited=traction_limited,
            wheel_force_n=wheel_force,
            traction_limit_n=traction_limit,
            rolling_resistance_n=rolling,
            grade_force_n=grade,
            acceleration_force_n=acceleration,
            explanation=(
                f"{spec.weight_g:.0f}g, tyre {spec.tire_diameter_mm:.1f}mm, "
                f"gear {spec.gear_ratio:.2f}:1, grade {spec.grade_angle_deg:.1f}°"
            ),
        )

    @staticmethod
    def margin(motor_torque_gcm: float, required_torque_gcm: float) -> tuple[float, float]:
        required = max(0.0, required_torque_gcm)
        margin = float(motor_torque_gcm) - required
        percent = 0.0 if required <= 0 else margin / required * 100.0
        return margin, percent

    def torque_for_weight(
        self,
        weight_g: float,
        *,
        tire_diameter_mm: float = 24.0,
        gear_ratio: float = 3.5,
        tire_course_mu: float = 0.90,
        rolling_resistance: float = 0.02,
        grade_angle_deg: float = 0.0,
        grade_length_mm: float = 0.0,
        acceleration_mps2: float = 0.0,
        drivetrain_efficiency: float = 0.85,
        traction_margin: float = 0.90,
    ) -> RequiredTorqueResult:
        return self.calculate(VehicleSpec(
            weight_g=weight_g,
            tire_diameter_mm=tire_diameter_mm,
            gear_ratio=gear_ratio,
            tire_course_mu=tire_course_mu,
            rolling_resistance=rolling_resistance,
            grade_angle_deg=grade_angle_deg,
            grade_length_mm=grade_length_mm,
            acceleration_mps2=acceleration_mps2,
            drivetrain_efficiency=drivetrain_efficiency,
            traction_margin=traction_margin,
        ))
