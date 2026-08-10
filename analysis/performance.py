"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 analysis/performance.py
=====================================================

Performance Analysis

FeatureSetからモーター性能を推定する。

責務
------
・推定RPM
・推定トルク
・推定対応車重

Measurementは変更しない。
"""

from __future__ import annotations

from typing import Any

from analysis.models import (
    EstimatedValue,
    FeatureSet,
    PerformanceResult,
)
from analysis.vehicle_weight import estimate_vehicle_weight


class PerformanceAnalysis:
    """モーター性能解析。"""

    def __init__(self, config: dict[str, Any]):
        self.config = config

    def analyze(self, features: FeatureSet) -> PerformanceResult:
        result = PerformanceResult()
        performance = self.config["performance"]
        rpm_cfg = performance["rpm"]
        torque_cfg = performance["torque"]
        weight_cfg = performance["weight"]

        # RPM
        rpm = features.rpm
        if rpm <= 0:
            rpm = features.average_voltage * rpm_cfg["voltage_gain"]

        result.estimated_rpm = EstimatedValue(
            value=rpm,
            unit="rpm",
            confidence=rpm_cfg["default_confidence"],
        )

        # Torque
        # This remains the V3 heuristic used by the existing benchmark.
        # It is intentionally not presented as a direct physical torque
        # constant because motor-specific Kt is not measured by this device.
        torque = features.average_current * torque_cfg["current_gain"]

        result.estimated_torque = EstimatedValue(
            value=torque,
            unit="g·cm",
            confidence=torque_cfg["default_confidence"],
        )

        # Vehicle weight
        # Use the benchmark estimator rather than the old arbitrary
        # torque_gain multiplication.  The estimator is explicitly
        # provisional and assumes 24 mm tires / 3.5:1 gearing.
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

        # PerformanceResult currently exposes a single EstimatedValue for
        # weight.  Store the center value there; UI can expose the range from
        # the same calibration parameters when presenting the benchmark.
        result.estimated_weight = EstimatedValue(
            value=weight.center_g,
            unit="g",
            confidence=weight.confidence,
        )

        return result
