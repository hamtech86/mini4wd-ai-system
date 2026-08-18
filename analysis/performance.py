"""Motor performance analysis and vehicle-weight suitability."""

from __future__ import annotations

from typing import Any

from analysis.models import EstimatedValue, FeatureSet, PerformanceResult
from analysis.vehicle_weight import estimate_vehicle_weight
from analysis.weight_suitability import WeightSuitabilityAnalysis


class PerformanceAnalysis:
    """Estimate motor RPM/torque and expose the weight-suitability result."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.weight_suitability = WeightSuitabilityAnalysis(config)

    def analyze(self, features: FeatureSet) -> PerformanceResult:
        result = PerformanceResult()
        performance = self.config["performance"]
        rpm_cfg = performance["rpm"]
        torque_cfg = performance["torque"]
        weight_cfg = performance["weight"]

        rpm = features.rpm
        if rpm <= 0:
            rpm = features.average_voltage * rpm_cfg["voltage_gain"]

        result.estimated_rpm = EstimatedValue(
            value=rpm,
            unit="rpm",
            confidence=rpm_cfg["default_confidence"],
        )

        # V3 benchmark heuristic. Motor-specific Kt is not directly measured.
        torque = features.average_current * torque_cfg["current_gain"]
        result.estimated_torque = EstimatedValue(
            value=torque,
            unit="g·cm",
            confidence=torque_cfg["default_confidence"],
        )

        # Keep the existing center/range estimate for backward compatibility.
        weight = estimate_vehicle_weight(
            torque,
            reference_torque_gcm=weight_cfg.get("reference_torque_gcm", 0.83),
            reference_weight_g=weight_cfg.get("reference_weight_g", 130.0),
            lower_factor=weight_cfg.get("lower_factor", 0.75),
            upper_factor=weight_cfg.get("upper_factor", 1.25),
            tire_diameter_mm=weight_cfg.get("tire_diameter_mm", 24.0),
            gear_ratio=weight_cfg.get("gear_ratio", 3.5),
            confidence=weight_cfg.get("default_confidence", 0.40),
        )
        result.estimated_weight = EstimatedValue(
            value=weight.center_g,
            unit="g",
            confidence=weight.confidence,
        )

        # Authoritative operator-facing suitability contract.
        result.weight_suitability = self.weight_suitability.analyze(torque)

        return result
