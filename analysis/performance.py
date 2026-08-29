"""Performance estimation from measured motor voltage/current."""
from __future__ import annotations

from typing import Any

from analysis.models import EstimatedValue, FeatureSet, PerformanceResult


class PerformanceAnalysis:
    """Estimate the mandatory Motor Analysis values from measured V/I.

    Cal7570 is the implementation baseline. Measured RPM is never consumed.
    Legacy gain fallbacks are intentionally absent: an unspecified coefficient
    must not silently become a newly invented formula.
    """

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

        # Canonical measured inputs: motor voltage and average current only.
        voltage = self._positive(features.average_voltage or features.voltage)
        current = self._positive(features.average_current or features.current)

        nominal_voltage = self._positive(motor_spec.get("nominal_voltage")) or 2.4
        nominal_rpm = self._positive(motor_spec.get("nominal_rpm"))
        nominal_current = self._positive(motor_spec.get("nominal_current_ma")) / 1000.0
        nominal_torque = self._positive(motor_spec.get("nominal_torque_gcm"))

        # Reference-voltage RPM. Measured RPM is deliberately ignored.
        rpm_30 = 0.0
        rpm_28 = 0.0
        if nominal_rpm > 0:
            rpm_30 = nominal_rpm * 3.0 / nominal_voltage
            rpm_28 = rpm_30 * (2.8 / 3.0)

        # Torque uses current_avg only. brush_peak_current is never used here.
        torque_30 = 0.0
        torque_28 = 0.0
        if nominal_current > 0 and nominal_torque > 0:
            torque_30 = nominal_torque * (current / nominal_current)
            torque_28 = torque_30 * (2.8 / 3.0)

        result.estimated_rpm_3v = EstimatedValue(rpm_30, "rpm", 0.50)
        result.estimated_rpm_28v = EstimatedValue(rpm_28, "rpm", 0.50)
        result.estimated_torque_3v = EstimatedValue(torque_30, "g·cm", 0.50)
        result.estimated_torque_28v = EstimatedValue(torque_28, "g·cm", 0.50)
        result.estimated_no_load_rpm = result.estimated_rpm_3v
        result.estimated_torque = result.estimated_torque_3v

        # Weight and brush-life coefficients are not numerically defined by
        # the commander specification. Do not use legacy constants or 130 g.
        result.estimated_supported_weight = EstimatedValue(0.0, "g", 0.0)
        return result
