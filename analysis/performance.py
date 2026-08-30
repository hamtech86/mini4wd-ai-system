"""Cal7570 motor performance estimation.

The command-tower specification is the sole source of the estimation path.
No legacy gain-based fallback and no fixed 130 g value are permitted.
"""
from __future__ import annotations

from typing import Any

from analysis.models import EstimatedValue, FeatureSet, PerformanceResult


class PerformanceAnalysis:
    """Estimate the four mandatory motor values from measured V/I data."""

    def __init__(self, config: dict[str, Any]):
        self.config = config

    @staticmethod
    def _positive(value: Any) -> float:
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return 0.0

    def analyze(
        self,
        features: FeatureSet,
        motor_spec: dict[str, Any] | None = None,
    ) -> PerformanceResult:
        result = PerformanceResult()
        motor_spec = motor_spec or {}

        # Individual estimate inputs. Measured RPM is never consumed.
        voltage = self._positive(features.average_voltage or features.voltage)
        current = self._positive(features.average_current or features.current)
        pwm = self._positive(features.pwm)
        brush_peak = self._positive(features.brush_peak_current)

        nominal_voltage = self._positive(motor_spec.get("nominal_voltage")) or 2.4
        nominal_rpm = self._positive(motor_spec.get("nominal_rpm"))
        nominal_current = self._positive(motor_spec.get("nominal_current_ma")) / 1000.0
        nominal_torque = self._positive(motor_spec.get("nominal_torque_gcm"))

        # Reference-voltage RPM estimate from the measured operating point.
        # PWM is used as the operating-point factor; measured RPM is not used.
        rpm_30 = 0.0
        rpm_28 = 0.0
        if nominal_rpm > 0 and nominal_voltage > 0:
            pwm_factor = pwm / 255.0 if pwm > 0 else 1.0
            rpm_measured_point = nominal_rpm * (voltage / nominal_voltage) * pwm_factor
            rpm_30 = rpm_measured_point * (3.0 / voltage) if voltage > 0 else 0.0
            rpm_28 = rpm_measured_point * (2.8 / voltage) if voltage > 0 else 0.0

        # Torque estimate from the measured V/I operating point.
        torque_30 = 0.0
        torque_28 = 0.0
        if nominal_current > 0 and nominal_torque > 0 and voltage > 0:
            torque_point = nominal_torque * (current / nominal_current) * (voltage / nominal_voltage)
            torque_30 = torque_point * (3.0 / voltage)
            torque_28 = torque_point * (2.8 / voltage)

        result.estimated_rpm_3v = EstimatedValue(rpm_30, "rpm", 0.50 if rpm_30 > 0 else 0.0)
        result.estimated_rpm_28v = EstimatedValue(rpm_28, "rpm", 0.50 if rpm_28 > 0 else 0.0)
        result.estimated_torque_3v = EstimatedValue(torque_30, "g·cm", 0.50 if torque_30 > 0 else 0.0)
        result.estimated_torque_28v = EstimatedValue(torque_28, "g·cm", 0.50 if torque_28 > 0 else 0.0)
        result.estimated_no_load_rpm = result.estimated_rpm_3v
        result.estimated_torque = result.estimated_torque_3v

        # These are intentionally left as explicit result fields. Their
        # calibration reference is supplied by the command-tower benchmark;
        # absence of that benchmark must not silently become a legacy formula.
        result.estimated_supported_weight = EstimatedValue(0.0, "g", 0.0)
        return result
