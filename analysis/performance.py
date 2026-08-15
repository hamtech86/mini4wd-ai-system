"""Performance estimation from measured voltage/current."""
from __future__ import annotations

from typing import Any

from analysis.models import EstimatedValue, FeatureSet, PerformanceResult


class PerformanceAnalysis:
    """Estimate no-load RPM, torque and supported vehicle weight.

    All three values are explicitly estimates. Measurement data is never
    modified and an input RPM field is intentionally not treated as measured
    RPM by this module.
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config

    def analyze(self, features: FeatureSet) -> PerformanceResult:
        result = PerformanceResult()
        performance = self.config["performance"]
        rpm_cfg = performance["rpm"]
        torque_cfg = performance["torque"]
        weight_cfg = performance["weight"]

        voltage = float(features.average_voltage or features.voltage or 0.0)
        current = float(features.average_current or features.current or 0.0)

        # Provisional no-load RPM estimate from motor voltage.
        rpm = max(0.0, voltage * float(rpm_cfg["voltage_gain"]))
        result.estimated_no_load_rpm = EstimatedValue(
            value=rpm,
            unit="rpm",
            confidence=float(rpm_cfg["default_confidence"]),
        )

        # Provisional torque estimate from motor current.
        torque = max(0.0, current * float(torque_cfg["current_gain"]))
        result.estimated_torque = EstimatedValue(
            value=torque,
            unit="g·cm",
            confidence=float(torque_cfg["default_confidence"]),
        )

        # Keep the existing configurable weight model as the provisional
        # supported-weight estimate until the vehicle-weight suitability
        # algorithm is calibrated against the 115–155 g reference set.
        supported_weight = max(0.0, torque * float(weight_cfg["torque_gain"]))
        result.estimated_supported_weight = EstimatedValue(
            value=supported_weight,
            unit="g",
            confidence=float(weight_cfg["default_confidence"]),
        )
        return result
