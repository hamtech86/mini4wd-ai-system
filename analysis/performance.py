"""Performance estimation from raw measurements and motor nominal values."""
from __future__ import annotations

from typing import Any, Optional

from analysis.models import EstimatedValue, FeatureSet, PerformanceResult


class PerformanceAnalysis:
    """Estimate motor torque and supported weight from measured current."""

    DEFINITION_VERSION = "torque-weight-v6-estimated-current"

    def __init__(self, config: dict[str, Any]):
        self.config = config

    @staticmethod
    def _model_value(model: Optional[dict[str, Any]], key: str):
        if not model:
            return None
        value = model.get(key)
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _measurement_value(features: FeatureSet, *names: str) -> Optional[float]:
        for name in names:
            value = getattr(features, name, None)
            try:
                if value is not None:
                    return float(value)
            except (TypeError, ValueError):
                continue
        return None

    def analyze(
        self,
        features: FeatureSet,
        motor_model: Optional[dict[str, Any]] = None,
    ) -> PerformanceResult:
        """Estimate torque from RAW LOG average current.

        This is explicitly an estimate, not a direct torque measurement.
        The torque-per-current coefficient is derived from the motor model's
        nominal torque and nominal current, then applied to the RAW LOG
        average motor current.
        """
        result = PerformanceResult()
        performance = self.config.get("performance", {})
        reference = performance.get("reference_vehicle", {})
        torque_config = performance.get("torque", {})
        weight_config = performance.get("weight", {})

        measured_rpm = self._measurement_value(features, "rpm", "average_rpm")
        measured_current = self._measurement_value(
            features, "average_current", "current"
        )
        measured_voltage = self._measurement_value(
            features, "average_voltage", "motor_voltage", "voltage"
        )

        nominal_torque = self._model_value(motor_model, "nominal_torque_gcm")
        if nominal_torque is None:
            nominal_torque = self._model_value(motor_model, "torque_gcm")

        nominal_current_ma = self._model_value(motor_model, "nominal_current_ma")
        if nominal_current_ma is None:
            nominal_current_ma = self._model_value(motor_model, "current_ma")

        nominal_current_a = (
            nominal_current_ma / 1000.0
            if nominal_current_ma is not None and nominal_current_ma > 0
            else None
        )

        rpm = max(0.0, measured_rpm or 0.0)
        result.estimated_no_load_rpm = EstimatedValue(
            value=rpm,
            unit="rpm",
            confidence=1.0 if measured_rpm is not None else 0.0,
        )

        torque_coefficient = None
        if nominal_torque is not None and nominal_current_a:
            torque_coefficient = nominal_torque / nominal_current_a

        if measured_current is not None and torque_coefficient is not None:
            # v6: RAW LOG average current × nominal torque / nominal current.
            torque = max(0.0, measured_current) * torque_coefficient
            torque_source = "RAW_CURRENT_X_NOMINAL_TORQUE_CURRENT_COEFFICIENT"
            torque_confidence = float(
                torque_config.get("default_confidence", 0.6)
            )
        elif nominal_torque is not None:
            torque = max(0.0, nominal_torque)
            torque_source = "MOTOR_MODEL_NOMINAL_TORQUE_FALLBACK"
            torque_confidence = float(
                torque_config.get("fallback_confidence", 0.3)
            )
        else:
            torque = 0.0
            torque_source = "UNAVAILABLE_NO_NOMINAL_TORQUE"
            torque_confidence = 0.0

        result.estimated_torque = EstimatedValue(
            value=torque,
            unit="g·cm",
            confidence=torque_confidence,
        )
        result.available_torque = EstimatedValue(
            value=torque,
            unit="g·cm",
            confidence=torque_confidence,
        )

        # The v6 weight conversion is configuration-owned. Do not use a
        # vehicle's observed/test weight as an input to the calculation.
        torque_to_weight = float(
            weight_config.get("torque_to_weight_g_per_gcm", 0.0)
        )
        supported_weight = max(0.0, torque * torque_to_weight)
        result.estimated_supported_weight = EstimatedValue(
            value=supported_weight,
            unit="g",
            confidence=torque_confidence,
        )

        result.weight_profile = [
            {
                "weight_g": float(weight),
                "required_torque_gcm": (
                    float(weight) / torque_to_weight
                    if torque_to_weight > 0
                    else 0.0
                ),
            }
            for weight in reference.get("weight_profile_g", [])
        ]
        result.weight_suitability = {
            "status": (
                "CALCULATED_FROM_ESTIMATED_TORQUE"
                if torque_confidence > 0 and torque_to_weight > 0
                else "UNAVAILABLE_NO_TORQUE_TO_WEIGHT_CONVERSION"
            ),
            "reason": (
                "Torque is estimated from RAW LOG average current using the "
                "motor-model nominal torque/current coefficient. Supported "
                "weight is calculated from the configured v6 torque-to-weight conversion."
            ),
            "gear_ratio": float(reference.get("gear_ratio", 3.5)),
            "tire_diameter_mm": float(reference.get("tire_diameter_mm", 24.0)),
            "course_considered": False,
            "measured_voltage_v": measured_voltage,
            "measured_current_a": measured_current,
            "measured_rpm": measured_rpm,
            "nominal_torque_gcm": nominal_torque,
            "nominal_current_a": nominal_current_a,
            "torque_coefficient_gcm_per_a": torque_coefficient,
            "torque_gcm": torque,
            "torque_source": torque_source,
            "torque_to_weight_g_per_gcm": torque_to_weight,
            "definition_version": self.DEFINITION_VERSION,
        }
        return result
