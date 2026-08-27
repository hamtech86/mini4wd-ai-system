"""Performance estimation from measured data and Motor Model master data."""
from __future__ import annotations

from typing import Any, Optional

from analysis.models import EstimatedValue, FeatureSet, PerformanceResult


class PerformanceAnalysis:
    """Estimate motor performance without inventing unsupported precision."""

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

        voltage = float(features.average_voltage or features.voltage or 0.0)
        current = abs(float(features.average_current or features.current or 0.0))

        # RPM priority: measured RPM -> Motor Model nominal RPM -> unavailable.
        # Do not turn voltage into a fabricated RPM value.
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
        # The former fixed current*10 fallback is intentionally removed.
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

        # Vehicle weight is not a motor-only physical constant. The former
        # arbitrary torque*12 conversion is therefore not exposed as a precise
        # parameter until a validated vehicle/course model exists.
        result.estimated_supported_weight = EstimatedValue(
            value=0.0,
            unit="g",
            confidence=0.0,
        )
        return result
