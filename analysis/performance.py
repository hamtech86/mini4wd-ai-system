"""Rebuilt Motor Analysis performance calculations.

This module is intentionally independent of the deleted legacy gain logic.
Inputs are measured motor voltage/current and motor-model reference data.
Measured RPM is never used.
"""
from __future__ import annotations

from typing import Any

from analysis.models import EstimatedValue, FeatureSet, PerformanceResult


ATOMIC_BRUSH_PEAK_REFERENCE_A = 1.498
SUPPORTED_WEIGHT_REFERENCE_G = 130.0
SUPPORTED_WEIGHT_REFERENCE_TORQUE_GCM = 121.2


class PerformanceAnalysis:
    """Calculate the four mandatory motor estimates."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    @staticmethod
    def _num(value: Any) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def analyze(
        self,
        features: FeatureSet,
        motor_spec: dict[str, Any] | None = None,
    ) -> PerformanceResult:
        spec = motor_spec or {}
        v = self._num(features.average_voltage or features.voltage)
        i = self._num(features.average_current or features.current)
        nominal_v = self._num(spec.get("nominal_voltage")) or 2.4
        nominal_rpm = self._num(spec.get("nominal_rpm"))
        nominal_i = self._num(spec.get("nominal_current_ma")) / 1000.0
        nominal_t = self._num(spec.get("nominal_torque_gcm"))
        brush_peak = self._num(features.brush_peak_current)

        result = PerformanceResult()

        # 1) Individual no-load RPM estimate from measured motor voltage.
        #    Reference-voltage values are independently normalized to 3.0 V and 2.8 V.
        rpm_at_measured_v = (
            nominal_rpm * v / nominal_v if nominal_rpm > 0 and nominal_v > 0 and v > 0 else 0.0
        )
        rpm_3v = rpm_at_measured_v * 3.0 / v if v > 0 else 0.0
        rpm_28v = rpm_at_measured_v * 2.8 / v if v > 0 else 0.0

        # 2) Individual torque estimate from measured average current and the
        #    motor-model nominal torque/current relationship. Brush peak current
        #    is deliberately excluded from torque calculation.
        torque_measured = (
            i * nominal_t / nominal_i if nominal_i > 0 and nominal_t > 0 else 0.0
        )
        torque_3v = torque_measured
        torque_28v = torque_measured

        # 3) Brush peak life-cycle index. Atomic Tune is the 100-point reference.
        #    This is an index (%), not an invented absolute cycle count.
        brush_life = (
            ATOMIC_BRUSH_PEAK_REFERENCE_A / brush_peak * 100.0
            if brush_peak > 0
            else 0.0
        )

        # 4) Supported-weight estimate from the established torque/weight anchor.
        #    121.2 g·cm corresponds to 130 g.
        weight = (
            torque_3v * SUPPORTED_WEIGHT_REFERENCE_G / SUPPORTED_WEIGHT_REFERENCE_TORQUE_GCM
            if torque_3v > 0
            else 0.0
        )

        confidence = 1.0 if (v > 0 and i >= 0 and nominal_rpm > 0 and nominal_i > 0 and nominal_t > 0) else 0.0
        brush_confidence = 1.0 if brush_peak > 0 else 0.0
        weight_confidence = confidence if torque_3v > 0 else 0.0

        result.estimated_rpm_3v = EstimatedValue(rpm_3v, "rpm", confidence)
        result.estimated_rpm_28v = EstimatedValue(rpm_28v, "rpm", confidence)
        result.estimated_torque_3v = EstimatedValue(torque_3v, "g·cm", confidence)
        result.estimated_torque_28v = EstimatedValue(torque_28v, "g·cm", confidence)
        result.estimated_no_load_rpm = result.estimated_rpm_3v
        result.estimated_torque = result.estimated_torque_3v
        result.brush_peak_life_cycle = EstimatedValue(brush_life, "%", brush_confidence)
        result.estimated_supported_weight = EstimatedValue(weight, "g", weight_confidence)
        return result
