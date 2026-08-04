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


class PerformanceAnalysis:
    """
    モーター性能解析
    """

    def __init__(
        self,
        config: dict[str, Any],
    ):

        self.config = config

    def analyze(
        self,
        features: FeatureSet,
    ) -> PerformanceResult:

        result = PerformanceResult()

        performance = self.config["performance"]

        rpm_cfg = performance["rpm"]

        torque_cfg = performance["torque"]

        weight_cfg = performance["weight"]

        #
        # RPM
        #

        rpm = features.rpm

        if rpm <= 0:

            rpm = (
                features.average_voltage
                * rpm_cfg["voltage_gain"]
            )

        result.estimated_rpm = EstimatedValue(

            value=rpm,

            unit="rpm",

            confidence=rpm_cfg[
                "default_confidence"
            ],
        )

        #
        # Torque
        #

        torque = (

            features.average_current

            * torque_cfg["current_gain"]

        )

        result.estimated_torque = EstimatedValue(

            value=torque,

            unit="g·cm",

            confidence=torque_cfg[
                "default_confidence"
            ],
        )

        #
        # Weight
        #

        weight = (

            torque

            * weight_cfg["torque_gain"]

        )

        result.estimated_weight = EstimatedValue(

            value=weight,

            unit="g",

            confidence=weight_cfg[
                "default_confidence"
            ],
        )

        return result

