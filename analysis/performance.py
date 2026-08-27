"""Performance estimation from measured voltage/current and Motor Model data."""
from __future__ import annotations

from typing import Any, Optional

from analysis.models import EstimatedValue, FeatureSet, PerformanceResult


class PerformanceAnalysis:
    """Estimate motor performance using measured features and master-model data."""

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

    def analyze(
        self,
        features: FeatureSet,
        motor_model: Optional[dict[str, Any]] = None,
    ) -> PerformanceResult:
        result = PerformanceResult()
        performance = self.config["performance"]
        rpm_cfg = performance["rpm"]
        weight_cfg = performance["weight"]

        voltage = float(features.average_voltage or features.voltage or 0.0)
        current = float(features.average_current or features.current or 0.0)

        # RPM remains an estimate from measured motor voltage until measured
        # RPM samples are available. If the master model has nominal RPM,
        # expose it as the model reference rather than silently replacing the
        # measurement-derived estimate.
        model_rpm = self._model_value(motor_model, "nominal_rpm")
        rpm = model_rpm if model_rpm and model_rpm > 0 else max(
            0.0, voltage * float(rpm_cfg["voltage_gain"])
        )
        rpm_confidence = (
            self._model_value(motor_model, "data_confidence")
            if model_rpm and model_rpm > 0 else float(rpm_cfg["default_confidence"])
        )
        result.estimated_no_load_rpm = EstimatedValue(
            value=rpm,
            unit="rpm",
            confidence=max(0.0, min(1.0, float(rpm_confidence or 0.0))),
        )

        # Torque coefficient is derived ONLY from the selected Motor Model:
        # nominal_torque_gcm / nominal_current_A. The old UI/config fallback
        # (current * 10) is intentionally not used anymore.
        nominal_torque = self._model_value(motor_model, "nominal_torque_gcm")
        nominal_current_ma = self._model_value(motor_model, "nominal_current_ma")
        torque_confidence = self._model_value(motor_model, "data_confidence") or 0.0
        if nominal_torque and nominal_torque > 0 and nominal_current_ma and nominal_current_ma > 0:
            torque_coefficient = nominal_torque / (nominal_current_ma / 1000.0)
            torque = max(0.0, current * torque_coefficient)
            result.estimated_torque = EstimatedValue(
                value=torque,
                unit="g·cm",
                confidence=max(0.0, min(1.0, torque_confidence)),
            )
        else:
            # No model data means no defensible torque estimate.
            result.estimated_torque = EstimatedValue(
                value=0.0,
                unit="g·cm",
                confidence=0.0,
            )

        # Weight is still explicitly provisional and can only be calculated
        # when a model-based torque estimate exists.
        torque = result.estimated_torque.value
        supported_weight = (
            max(0.0, torque * float(weight_cfg["torque_gain"]))
            if torque > 0 else 0.0
        )
        result.estimated_supported_weight = EstimatedValue(
            value=supported_weight,
            unit="g",
            confidence=(
                float(weight_cfg["default_confidence"])
                if supported_weight > 0 else 0.0
            ),
        )
        return result
