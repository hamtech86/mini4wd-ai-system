"""Performance estimation from measured motor voltage/current."""
from __future__ import annotations

from typing import Any

from analysis.models import EstimatedValue, FeatureSet, PerformanceResult


class PerformanceAnalysis:
    """Estimate motor performance from measurement-derived V/I features.

    All RPM/torque/weight outputs are estimates. Measured RPM is never used.
    The formal 3.0 V / 2.8 V conversion definitions and supported-weight
    model are maintained separately from the UI.
    """

    def __init__(self, config: dict[str, Any]):
        self.config = config

    @staticmethod
    def _positive(value: Any) -> float:
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return 0.0

    def analyze(self, features: FeatureSet, motor_spec: dict[str, Any] | None = None) -> PerformanceResult:
        """Return provisional reference-voltage estimates.

        NOTE: This method intentionally does not invent a physical supported-
        weight coefficient. Until the audited weight definition is restored,
        weight is derived only through the configured analysis contract.
        """
        result = PerformanceResult()
        motor_spec = motor_spec or {}

        voltage = self._positive(features.average_voltage or features.voltage)
        current = self._positive(features.average_current or features.current)

        nominal_voltage = self._positive(motor_spec.get("nominal_voltage")) or 2.4
        nominal_rpm = self._positive(motor_spec.get("nominal_rpm"))
        nominal_current = self._positive(motor_spec.get("nominal_current_ma")) / 1000.0
        nominal_torque = self._positive(motor_spec.get("nominal_torque_gcm"))

        # RPM is a reference-voltage estimate from the selected motor model.
        # No measured RPM field is consumed.
        if nominal_rpm > 0 and nominal_voltage > 0:
            rpm_30 = nominal_rpm * 3.0 / nominal_voltage
            rpm_28 = nominal_rpm * 2.8 / nominal_voltage
        else:
            gain = self._positive(self.config.get("performance", {}).get("rpm", {}).get("voltage_gain"))
            rpm_30 = 3.0 * gain if gain > 0 else 0.0
            rpm_28 = 2.8 * gain if gain > 0 else 0.0

        # Do not use brush_peak_current as motor torque. In MOTOR_BREAKIN_V3
        # it is a brush-event peak, not a calibrated shaft-load current.
        if nominal_current > 0 and nominal_torque > 0:
            torque_reference = current * nominal_torque / nominal_current
        else:
            gain = self._positive(self.config.get("performance", {}).get("torque", {}).get("current_gain"))
            torque_reference = current * gain

        # Keep the two reference voltages independent. The measured benchmark
        # voltage is not substituted for the requested reference voltage.
        torque_30 = torque_reference * 3.0 / nominal_voltage if nominal_voltage > 0 else 0.0
        torque_28 = torque_reference * 2.8 / nominal_voltage if nominal_voltage > 0 else 0.0

        result.estimated_rpm_3v = EstimatedValue(rpm_30, "rpm", 0.50)
        result.estimated_rpm_28v = EstimatedValue(rpm_28, "rpm", 0.50)
        result.estimated_torque_3v = EstimatedValue(torque_30, "g·cm", 0.50)
        result.estimated_torque_28v = EstimatedValue(torque_28, "g·cm", 0.50)
        result.estimated_no_load_rpm = result.estimated_rpm_3v
        result.estimated_torque = result.estimated_torque_3v

        # The supported-weight coefficient is deliberately not hard-coded here.
        # It must come from the audited physical/reference definition rather
        # than an arbitrary torque-to-gram multiplier.
        weight_gain = self._positive(self.config.get("performance", {}).get("weight", {}).get("torque_gain"))
        result.estimated_supported_weight = EstimatedValue(
            max(0.0, torque_30 * weight_gain), "g", 0.40
        )
        return result
