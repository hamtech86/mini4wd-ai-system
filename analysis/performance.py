"""Motor performance analysis and vehicle-weight suitability."""

from __future__ import annotations

from typing import Any

from analysis.models import EstimatedValue, FeatureSet, PerformanceResult
from analysis.weight_suitability import WeightSuitabilityAnalysis


class PerformanceAnalysis:
    """Estimate motor RPM/torque and map torque to vehicle weight suitability."""

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
            value=rpm, unit="rpm", confidence=rpm_cfg["default_confidence"]
        )

        torque = features.average_current * torque_cfg["current_gain"]
        result.estimated_torque = EstimatedValue(
            value=torque, unit="g·cm", confidence=torque_cfg["default_confidence"]
        )

        # Legacy field retained for compatibility. The new suitability model
        # must not use this linear torque->weight conversion as its result.
        weight = torque * weight_cfg["torque_gain"]
        result.estimated_weight = EstimatedValue(
            value=weight, unit="g", confidence=weight_cfg["default_confidence"]
        )
        result.weight_suitability = self.weight_suitability.analyze(torque)
        return result
