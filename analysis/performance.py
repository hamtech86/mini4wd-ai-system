"""Motor performance analysis and vehicle-weight suitability."""

from __future__ import annotations

from typing import Any, Optional

from analysis.models import EstimatedValue, FeatureSet, PerformanceResult
from analysis.weight_suitability import WeightSuitabilityAnalysis


class PerformanceAnalysis:
    """Estimate motor performance from measurements plus Motor Model data."""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.weight_suitability = WeightSuitabilityAnalysis(config)

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
        performance = self.config.get("performance", {})
        rpm_cfg = performance.get("rpm", {})
        torque_cfg = performance.get("torque", {})

        current = abs(float(features.average_current or features.current or 0.0))

        # Measured RPM has priority. Motor Model nominal RPM is the fallback.
        # Voltage is never converted directly into RPM.
        measured_rpm = float(features.rpm or 0.0)
        model_rpm = self._model_value(motor_model, "nominal_rpm")
        model_confidence = self._confidence(
            self._model_value(motor_model, "data_confidence"),
            self._confidence(rpm_cfg.get("default_confidence"), 0.0),
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
            value=rpm, unit="rpm", confidence=rpm_confidence
        )

        # Individual operating-point torque is provisional. Motor Model supplies
        # the torque/current coefficient and the measurement supplies current.
        nominal_torque = self._model_value(motor_model, "nominal_torque_gcm")
        nominal_current_ma = self._model_value(motor_model, "nominal_current_ma")
        if (
            nominal_torque is not None and nominal_torque > 0
            and nominal_current_ma is not None and nominal_current_ma > 0
        ):
            torque_coefficient = nominal_torque / (nominal_current_ma / 1000.0)
            estimated_torque = max(0.0, current * torque_coefficient)
            torque_confidence = model_confidence
        else:
            # Keep the old configurable fallback for models that do not expose
            # nominal current/torque, but mark its confidence from config.
            current_gain = float(torque_cfg.get("current_gain", 0.0) or 0.0)
            estimated_torque = max(0.0, current * current_gain)
            torque_confidence = self._confidence(
                torque_cfg.get("default_confidence"), 0.0
            ) if current_gain > 0 else 0.0

        result.estimated_torque = EstimatedValue(
            value=estimated_torque, unit="g·cm", confidence=torque_confidence
        )

        # Supported weight MUST NOT be inferred from break-in current. A low-PWM
        # break-in sample is not a calibrated load point. Use the Motor Model's
        # torque capability as the available torque for the benchmark suitability
        # profile (115–155 g, 5 g steps, 24 mm / 3.5:1).
        available_torque = max(0.0, nominal_torque or 0.0)
        result.available_torque = EstimatedValue(
            value=available_torque,
            unit="g·cm",
            confidence=model_confidence if available_torque > 0 else 0.0,
        )

        suitability = self.weight_suitability.analyze(available_torque)
        result.weight_suitability = suitability
        result.weight_profile = [
            {
                "weight_g": point.weight_g,
                "required_torque_gcm": point.required_torque_gcm,
                "available_torque_gcm": point.available_torque_gcm,
                "surplus_torque_gcm": point.surplus_torque_gcm,
                "torque_margin": point.torque_margin,
                "supported": 1.0 if point.status != "UNSUITABLE" else 0.0,
            }
            for point in suitability.points
        ]

        reference_point = next(
            (point for point in suitability.points
             if point.weight_g == suitability.current_reference_g),
            None,
        )
        result.required_torque_130g = EstimatedValue(
            value=reference_point.required_torque_gcm if reference_point else 0.0,
            unit="g·cm",
            confidence=1.0 if reference_point else 0.0,
        )
        result.torque_margin_130g = EstimatedValue(
            value=reference_point.torque_margin if reference_point else 0.0,
            unit="ratio",
            confidence=suitability.confidence if reference_point else 0.0,
        )

        # The mandatory UI value is always numeric. It is the highest configured
        # weight classified as usable; 0 means none of the configured points is
        # supported by the Motor Model capability.
        result.estimated_supported_weight = EstimatedValue(
            value=suitability.upper_limit_g,
            unit="g",
            confidence=suitability.confidence if available_torque > 0 else 0.0,
        )
        return result
