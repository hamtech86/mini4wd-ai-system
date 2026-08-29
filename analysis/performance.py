"""Performance estimation from raw measurements and explicit physical inputs."""
from __future__ import annotations

from typing import Any, Optional

from analysis.models import EstimatedValue, FeatureSet, PerformanceResult


class PerformanceAnalysis:
    """Analyze measured motor performance and convert torque to weight."""

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
        result = PerformanceResult()
        performance = self.config.get("performance", {})
        reference = performance.get("reference_vehicle", {})
        torque_config = performance.get("torque", {})
        weight_config = performance.get("weight", {})

        # RAW measurement-derived values remain the analysis source for
        # voltage/current/RPM. A torque value explicitly supplied by the
        # feature set is preferred. If it is not present, use the motor
        # model's stored torque as the torque input rather than inventing a
        # current-to-torque conversion.
        measured_rpm = self._measurement_value(features, "rpm", "average_rpm")
        measured_current = self._measurement_value(
            features, "average_current", "current"
        )
        measured_voltage = self._measurement_value(
            features, "motor_voltage", "voltage"
        )
        measured_torque = self._measurement_value(
            features, "estimated_torque", "torque", "measured_torque"
        )
        model_torque = self._model_value(motor_model, "nominal_torque_gcm")
        if model_torque is None:
            model_torque = self._model_value(motor_model, "torque_gcm")

        rpm = max(0.0, measured_rpm or 0.0)
        result.estimated_no_load_rpm = EstimatedValue(
            value=rpm,
            unit="rpm",
            confidence=1.0 if measured_rpm is not None else 0.0,
        )

        torque = measured_torque if measured_torque is not None else model_torque
        torque_confidence = (
            1.0 if measured_torque is not None else
            float(torque_config.get("default_confidence", 0.0)) if model_torque is not None else 0.0
        )
        torque = max(0.0, float(torque or 0.0))
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

        # Simple project rule: supported weight is directly proportional to
        # torque. 130 g corresponds to 121.2 g·cm, so no vehicle samples or
        # course model are required for this display value.
        torque_to_weight = float(
            weight_config.get("torque_to_weight_g_per_gcm", 130.0 / 121.2)
        )
        supported_weight = torque * torque_to_weight
        result.estimated_supported_weight = EstimatedValue(
            value=supported_weight,
            unit="g",
            confidence=torque_confidence,
        )

        result.weight_profile = [
            {"weight_g": float(weight), "required_torque_gcm": float(weight) / torque_to_weight}
            for weight in reference.get("weight_profile_g", [])
        ]
        result.weight_suitability = {
            "status": "CALCULATED_FROM_TORQUE" if torque_confidence > 0 else "UNAVAILABLE_NO_TORQUE",
            "reason": "Supported weight is a direct torque-to-weight conversion.",
            "gear_ratio": float(reference.get("gear_ratio", 3.5)),
            "tire_diameter_mm": float(reference.get("tire_diameter_mm", 24.0)),
            "course_considered": False,
            "measured_voltage_v": measured_voltage,
            "measured_current_a": measured_current,
            "measured_rpm": measured_rpm,
            "torque_gcm": torque,
            "torque_to_weight_g_per_gcm": torque_to_weight,
            "definition_version": "torque-weight-v5-simple",
        }
        return result
