"""Performance estimation from measured data and Motor Model master data."""
from __future__ import annotations

from typing import Any, Optional

from analysis.models import EstimatedValue, FeatureSet, PerformanceResult


class PerformanceAnalysis:
    """Estimate motor performance using measured data and master-model data."""

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
    def _confidence(value: Any, default: float = 0.0) -> float:
        try:
            return max(0.0, min(1.0, float(value)))
        except (TypeError, ValueError):
            return default

    def analyze(
        self,
        features: FeatureSet,
        motor_model: Optional[dict[str, Any]] = None,
    ) -> PerformanceResult:
        result = PerformanceResult()
        performance = self.config["performance"]
        reference = performance.get("reference_vehicle", {})
        reference_gear = float(reference.get("gear_ratio", 3.5))
        reference_tire = float(reference.get("tire_diameter_mm", 24.0))

        current = abs(float(features.average_current or features.current or 0.0))

        # RPM priority: measured RPM -> Motor Model nominal RPM -> unavailable.
        measured_rpm = float(features.rpm or 0.0)
        model_rpm = self._model_value(motor_model, "nominal_rpm")
        model_confidence = self._confidence(
            self._model_value(motor_model, "data_confidence"), 0.0
        )
        if measured_rpm > 0:
            rpm = measured_rpm
            rpm_confidence = 1.0
        elif model_rpm is not None and model_rpm > 0:
            rpm = model_rpm
            rpm_confidence = model_confidence
        else:
            rpm = 0.0
            rpm_confidence = 0.0

        result.estimated_no_load_rpm = EstimatedValue(
            value=rpm,
            unit="rpm",
            confidence=rpm_confidence,
        )

        # Torque coefficient comes ONLY from the selected Motor Model:
        # nominal_torque_gcm / nominal_current_A.
        nominal_torque = self._model_value(motor_model, "nominal_torque_gcm")
        nominal_current_ma = self._model_value(motor_model, "nominal_current_ma")
        if (nominal_torque is not None and nominal_torque > 0 and
                nominal_current_ma is not None and nominal_current_ma > 0):
            torque_coefficient = nominal_torque / (nominal_current_ma / 1000.0)
            torque = max(0.0, current * torque_coefficient)
            result.estimated_torque = EstimatedValue(
                value=torque,
                unit="g·cm",
                confidence=model_confidence,
            )
        else:
            result.estimated_torque = EstimatedValue(
                value=0.0,
                unit="g·cm",
                confidence=0.0,
            )

        # Reference vehicle calculation.
        # Only gear ratio and tire diameter are considered. The baseline
        # coefficient is retained as the system's reference calibration:
        # at 3.5:1 and 24 mm, 1 g·cm corresponds to 12 g of reference weight.
        # This is a reference index, not a claim of physically supported mass.
        torque = result.estimated_torque.value
        baseline_weight_per_torque = 12.0
        if torque > 0 and reference_gear > 0 and reference_tire > 0:
            gear_factor = reference_gear / 3.5
            tire_factor = 24.0 / reference_tire
            supported_weight = torque * baseline_weight_per_torque * gear_factor * tire_factor
            weight_confidence = model_confidence
        else:
            supported_weight = 0.0
            weight_confidence = 0.0

        result.estimated_supported_weight = EstimatedValue(
            value=max(0.0, supported_weight),
            unit="g",
            confidence=weight_confidence,
        )
        return result
