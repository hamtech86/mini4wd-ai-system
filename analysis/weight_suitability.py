"""Motor weight-suitability analysis for MOTOR_BREAKIN_V3.

This layer converts the existing benchmark torque estimate into a structured
115-155 g suitability profile.  It is intentionally a configurable benchmark
model; the UI must only display the result and must not recalculate it.
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
    points: tuple[WeightSuitabilityPoint, ...]
    confidence: float
    tire_diameter_mm: float
    gear_ratio: float
    basis: str


class WeightSuitabilityAnalysis:
    """Build the operator-facing compatible-weight profile from torque."""

    def __init__(self, config: dict[str, Any]):
        cfg = config.get("performance", {}).get("weight_suitability", {})
        self.min_weight_g = float(cfg.get("min_weight_g", 115.0))
        self.max_weight_g = float(cfg.get("max_weight_g", 155.0))
        self.step_g = float(cfg.get("step_g", 5.0))
        self.reference_torque_gcm = float(cfg.get("reference_torque_gcm", 0.83))
        self.reference_weight_g = float(cfg.get("reference_weight_g", 130.0))
        self.comparison_weight_g = float(cfg.get("comparison_weight_g", 140.0))
        self.tire_diameter_mm = float(cfg.get("tire_diameter_mm", 24.0))
        self.gear_ratio = float(cfg.get("gear_ratio", 3.5))
        self.confidence = float(cfg.get("default_confidence", 0.40))
        self.margin_recommended = float(cfg.get("margin_recommended", 1.15))
        self.margin_acceptable = float(cfg.get("margin_acceptable", 1.00))
        self.margin_limit = float(cfg.get("margin_limit", 0.90))

    def analyze(self, available_torque_gcm: float) -> WeightSuitabilityResult:
        available = max(0.0, float(available_torque_gcm))
        points: list[WeightSuitabilityPoint] = []
        weight = self.min_weight_g
        step = max(0.1, self.step_g)

        while weight <= self.max_weight_g + 1e-9:
            required = self.required_torque(weight)
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
            points.append(
                WeightSuitabilityPoint(
                    weight_g=round(weight, 1),
                    required_torque_gcm=required,
                    available_torque_gcm=available,
                    surplus_torque_gcm=surplus,
                    torque_margin=margin,
                    status=status,
                )
            )
            weight += step

        recommended = [p.weight_g for p in points if p.status == "RECOMMENDED"]
        acceptable = [
            p.weight_g for p in points
            if p.status in {"RECOMMENDED", "ACCEPTABLE"}
        ]
        usable = acceptable or [p.weight_g for p in points if p.status == "LIMIT"]

        return WeightSuitabilityResult(
            recommended_min_g=min(recommended) if recommended else (min(usable) if usable else 0.0),
            recommended_max_g=max(recommended) if recommended else 0.0,
            upper_limit_g=max(usable) if usable else 0.0,
            current_reference_g=self.reference_weight_g,
            comparison_weight_g=self.comparison_weight_g,
            points=tuple(points),
            confidence=self.confidence,
            tire_diameter_mm=self.tire_diameter_mm,
            gear_ratio=self.gear_ratio,
            basis="Benchmark torque calibration; 24 mm tire / 3.5:1 gearing; course, roller, brake and grip factors excluded",
        )

    def required_torque(self, weight_g: float) -> float:
        """Return calibrated required motor torque for a target vehicle weight."""
        reference = max(1e-9, self.reference_weight_g)
        return max(0.0, self.reference_torque_gcm) * max(0.0, float(weight_g)) / reference
