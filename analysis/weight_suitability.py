"""Vehicle weight suitability analysis for MOTOR_BREAKIN_V3.

Converts estimated motor torque into a practical vehicle-weight profile.
The first version deliberately keeps the model small and configurable so it
can be calibrated against real Mini 4WD runs later.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class WeightSuitabilityPoint:
    weight_g: float
    required_torque_gcm: float
    available_torque_gcm: float
    surplus_torque_gcm: float
    torque_margin: float
    status: str


@dataclass(frozen=True)
class WeightSuitabilityResult:
    recommended_min_g: float
    recommended_max_g: float
    upper_limit_g: float
    current_reference_g: float
    comparison_weight_g: float
    points: list[WeightSuitabilityPoint]
    target_acceleration_mps2: float
    drivetrain_efficiency: float
    tire_diameter_mm: float
    gear_ratio: float


class WeightSuitabilityAnalysis:
    """Estimate suitable vehicle weight from available motor torque."""

    TORQUE_GCM_PER_NM = 10197.162129779

    def __init__(self, config: dict[str, Any]):
        cfg = config.get("performance", {}).get("weight_suitability", {})
        self.min_weight_g = float(cfg.get("min_weight_g", 115.0))
        self.max_weight_g = float(cfg.get("max_weight_g", 155.0))
        self.step_g = float(cfg.get("step_g", 5.0))
        self.reference_weight_g = float(cfg.get("reference_weight_g", 130.0))
        self.comparison_weight_g = float(cfg.get("comparison_weight_g", 140.0))
        self.tire_diameter_mm = float(cfg.get("tire_diameter_mm", 24.0))
        self.gear_ratio = float(cfg.get("gear_ratio", 3.5))
        self.drivetrain_efficiency = float(cfg.get("drivetrain_efficiency", 0.75))
        self.target_acceleration_mps2 = float(cfg.get("target_acceleration_mps2", 3.0))
        self.margin_recommended = float(cfg.get("margin_recommended", 1.30))
        self.margin_acceptable = float(cfg.get("margin_acceptable", 1.10))
        self.margin_limit = float(cfg.get("margin_limit", 1.00))

    def analyze(self, available_torque_gcm: float) -> WeightSuitabilityResult:
        available = max(0.0, float(available_torque_gcm))
        points: list[WeightSuitabilityPoint] = []
        weight = self.min_weight_g
        while weight <= self.max_weight_g + 1e-9:
            required = self.required_motor_torque(weight)
            margin = available / required if required > 0 else float("inf")
            surplus = available - required
            if margin >= self.margin_recommended:
                status = "RECOMMENDED"
            elif margin >= self.margin_acceptable:
                status = "ACCEPTABLE"
            elif margin >= self.margin_limit:
                status = "LIMIT"
            else:
                status = "UNSUITABLE"
            points.append(WeightSuitabilityPoint(
                weight_g=round(weight, 1),
                required_torque_gcm=required,
                available_torque_gcm=available,
                surplus_torque_gcm=surplus,
                torque_margin=margin,
                status=status,
            ))
            weight += self.step_g

        recommended = [p.weight_g for p in points if p.status == "RECOMMENDED"]
        acceptable = [p.weight_g for p in points if p.status in {"RECOMMENDED", "ACCEPTABLE"}]
        usable = acceptable or [p.weight_g for p in points if p.status == "LIMIT"]
        return WeightSuitabilityResult(
            recommended_min_g=min(recommended) if recommended else (min(usable) if usable else 0.0),
            recommended_max_g=max(recommended) if recommended else 0.0,
            upper_limit_g=max(usable) if usable else 0.0,
            current_reference_g=self.reference_weight_g,
            comparison_weight_g=self.comparison_weight_g,
            points=points,
            target_acceleration_mps2=self.target_acceleration_mps2,
            drivetrain_efficiency=self.drivetrain_efficiency,
            tire_diameter_mm=self.tire_diameter_mm,
            gear_ratio=self.gear_ratio,
        )

    def required_motor_torque(self, weight_g: float) -> float:
        mass_kg = max(0.0, float(weight_g)) / 1000.0
        radius_m = self.tire_diameter_mm / 2000.0
        axle_torque_nm = mass_kg * self.target_acceleration_mps2 * radius_m
        motor_torque_nm = axle_torque_nm / (self.gear_ratio * self.drivetrain_efficiency)
        return motor_torque_nm * self.TORQUE_GCM_PER_NM
