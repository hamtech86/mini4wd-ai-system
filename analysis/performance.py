"""Performance estimation from measured motor voltage/current."""
from __future__ import annotations

from typing import Any

from analysis.models import EstimatedValue, FeatureSet, PerformanceResult


class PerformanceAnalysis:
    """Estimate RPM and torque from motor V/I measurements.

    Confirmed model:
      torque[g·cm] = average_current[A] * nominal_torque[g·cm] / nominal_current[A]
      supported_weight[g] = torque[g·cm] * 1.0726072607

    All performance values are estimates. Measured RPM is never used.
    """

    WEIGHT_PER_TORQUE = 1.0726072607

    def __init__(self, config: dict[str, Any]):
        self.config = config

    @staticmethod
    def _positive(value: Any) -> float:
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return 0.0

    def analyze(self, features: FeatureSet, motor_spec: dict[str, Any] | None = None) -> PerformanceResult:
        result = PerformanceResult()
        motor_spec = motor_spec or {}

        voltage = self._positive(features.average_voltage or features.voltage)
        current = self._positive(features.average_current or features.current)

        nominal_voltage = self._positive(motor_spec.get("nominal_voltage")) or 2.4
        nominal_rpm = self._positive(motor_spec.get("nominal_rpm"))
        nominal_current = self._positive(motor_spec.get("nominal_current_ma")) / 1000.0
        nominal_torque = self._positive(motor_spec.get("nominal_torque_gcm"))

        # RPM is an estimate derived from the motor nominal RPM and reference
        # voltage. No measured RPM field is consumed.
        rpm_cfg = self.config.get("performance", {}).get("rpm", {})
        gain = self._positive(rpm_cfg.get("voltage_gain"))
        if nominal_rpm > 0 and nominal_voltage > 0:
            rpm_30 = nominal_rpm * 3.0 / nominal_voltage
            rpm_28 = nominal_rpm * 2.8 / nominal_voltage
        elif voltage > 0:
            rpm_30 = voltage * gain * 3.0 / voltage
            rpm_28 = voltage * gain * 2.8 / voltage
        else:
            rpm_30 = rpm_28 = 0.0

        # Confirmed torque model. If nominal current/torque are not yet
        # populated in the motor master, retain the existing configurable
        # current-gain fallback so analysis does not stop.
        if nominal_current > 0 and nominal_torque > 0:
            torque = current * nominal_torque / nominal_current
        else:
            torque_gain = self._positive(
                self.config.get("performance", {}).get("torque", {}).get("current_gain")
            )
            torque = current * torque_gain

        # Reference-voltage estimates. The raw operating-point torque is
        # normalized to the requested reference voltage for user comparison.
        torque_30 = torque * 3.0 / voltage if voltage > 0 else 0.0
        torque_28 = torque * 2.8 / voltage if voltage > 0 else 0.0

        result.estimated_rpm_3v = EstimatedValue(rpm_30, "rpm", 0.50)
        result.estimated_rpm_28v = EstimatedValue(rpm_28, "rpm", 0.50)
        result.estimated_torque_3v = EstimatedValue(torque_30, "g·cm", 0.50)
        result.estimated_torque_28v = EstimatedValue(torque_28, "g·cm", 0.50)

        # Existing consumers continue to receive the 3.0 V estimate.
        result.estimated_no_load_rpm = result.estimated_rpm_3v
        result.estimated_torque = result.estimated_torque_3v
        result.estimated_supported_weight = EstimatedValue(
            max(0.0, torque_30 * self.WEIGHT_PER_TORQUE), "g", 0.50
        )
        return result
