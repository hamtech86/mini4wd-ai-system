"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 analysis/performance.py
=====================================================

Performance Analysis

Estimate motor performance from measured motor voltage/current.
KY-024 RPM is intentionally excluded from the formal estimate.
=====================================================
"""

from __future__ import annotations

from typing import Any

from analysis.models import EstimatedValue, FeatureSet, PerformanceResult


class PerformanceAnalysis:
    """Estimate no-load RPM, torque and corresponding vehicle weight."""

    def __init__(self, config: dict[str, Any]):
        self.config = config

    def analyze(self, features: FeatureSet) -> PerformanceResult:
        result = PerformanceResult()
        performance = self.config.get("performance", {})

        rpm_cfg = performance.get("rpm", {})
        torque_cfg = performance.get("torque", {})
        weight_cfg = performance.get("weight", {})

        measured_voltage = max(0.0, float(getattr(features, "average_voltage", 0.0)))
        measured_current = max(0.0, float(getattr(features, "average_current", 0.0)))

        kv = float(rpm_cfg.get("kv_rpm_per_volt", rpm_cfg.get("voltage_gain", 8500.0)))
        nominal_voltage = float(rpm_cfg.get("nominal_voltage", 2.4))
        max_valid_voltage = float(rpm_cfg.get("max_valid_voltage", 3.6))
        base_confidence = float(rpm_cfg.get("default_confidence", 0.50))

        # Formal RPM is estimated only from electrical measurements.
        # If the terminal-voltage measurement is outside the FA130 operating
        # range, use the model nominal voltage and explicitly lower confidence
        # instead of producing an absurd RPM from a bad sensor differential.
        voltage_for_rpm = measured_voltage
        confidence = base_confidence
        if voltage_for_rpm <= 0.05:
            voltage_for_rpm = nominal_voltage
            confidence *= 0.35
        elif voltage_for_rpm > max_valid_voltage:
            voltage_for_rpm = nominal_voltage
            confidence *= 0.35

        estimated_rpm = max(0.0, voltage_for_rpm * kv)
        result.estimated_rpm = EstimatedValue(
            value=estimated_rpm,
            unit="rpm",
            confidence=confidence,
        )

        # Torque is estimated from motor current via the motor torque constant.
        # Default is derived from ~8500 rpm/V (FA130-class Torque Tune baseline).
        kt = float(torque_cfg.get("torque_constant_gcm_per_a", 11.46))
        torque_confidence = float(torque_cfg.get("default_confidence", 0.50))
        estimated_torque = max(0.0, measured_current * kt)
        result.estimated_torque = EstimatedValue(
            value=estimated_torque,
            unit="g·cm",
            confidence=torque_confidence if measured_current > 0.02 else 0.20,
        )

        # Keep the existing corresponding-weight model as an explicit derived
        # estimate.  This is not a claim of exact raceable vehicle mass.
        weight_gain = float(weight_cfg.get("torque_gain", 12.0))
        weight_confidence = float(weight_cfg.get("default_confidence", 0.40))
        estimated_weight = estimated_torque * weight_gain
        result.estimated_weight = EstimatedValue(
            value=max(0.0, estimated_weight),
            unit="g",
            confidence=weight_confidence,
        )

        return result
