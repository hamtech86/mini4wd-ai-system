"""Performance estimation from measured voltage/current."""
from __future__ import annotations

from typing import Any

from analysis.models import EstimatedValue, FeatureSet, PerformanceResult


class PerformanceAnalysis:
    """Estimate motor performance without modifying Measurement data.

    RPM and torque are explicitly estimated values.  A physical RPM sensor is
    not required by the current MOTOR_BREAKIN_V3 specification, therefore an
    input ``features.rpm`` value is never treated as measured RPM here.
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config

    def analyze(self, features: FeatureSet) -> PerformanceResult:
        result = PerformanceResult()
        performance = self.config["performance"]
        rpm_cfg = performance["rpm"]
        torque_cfg = performance["torque"]
        weight_cfg = performance["weight"]

        # Current specification: estimated RPM is derived from voltage.
        voltage = float(features.average_voltage or features.voltage or 0.0)
        rpm = max(0.0, voltage * float(rpm_cfg["voltage_gain"]))
        result.estimated_rpm = EstimatedValue(
            value=rpm,
            unit="rpm",
            confidence=float(rpm_cfg["default_confidence"]),
        )

        # Current specification: estimated torque is derived from current.
        current = float(features.average_current or features.current or 0.0)
        torque = max(0.0, current * float(torque_cfg["current_gain"]))
        result.estimated_torque = EstimatedValue(
            value=torque,
            unit="g·cm",
            confidence=float(torque_cfg["default_confidence"]),
        )

        weight = max(0.0, torque * float(weight_cfg["torque_gain"]))
        result.estimated_weight = EstimatedValue(
            value=weight,
            unit="g",
            confidence=float(weight_cfg["default_confidence"]),
        )
        return result
