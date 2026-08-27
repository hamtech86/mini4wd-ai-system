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

        current = abs(float(features.average_current or features.current or 0.0))

        # RPM: measured RPM has priority. Otherwise use the Motor Model nominal
        # RPM as the no-load RPM estimate. Never derive RPM from voltage.
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

        # Operating torque estimate remains based on the Motor Model torque
        # coefficient and the measured current.
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

        # Supported weight is a defined reference metric, not a direct claim of
        # maximum race weight. It uses the Motor Model's rated/load torque,
        # because the unloaded running current cannot represent vehicle load.
        #
        # F_wheel(gf) = T_motor(gf*cm) * gear_ratio / tire_radius(cm)
        # m(g) = F_wheel(gf) * g(cm/s^2) / reference_acceleration(cm/s^2)
        #
        # The only vehicle inputs are the requested reference gear ratio 3.5:1
        # and tire diameter 24 mm. Drivetrain efficiency is deliberately 100%
        # in this baseline so no additional vehicle factor is introduced.
        gear_ratio = float(reference.get("gear_ratio", 3.5))
        tire_diameter_mm = float(reference.get("tire_diameter_mm", 24.0))
        reference_acceleration = float(reference.get("reference_acceleration_mps2", 3.0))
        tire_radius_cm = tire_diameter_mm / 20.0
        gravity_cm_s2 = 981.0
        rated_torque = nominal_torque if nominal_torque and nominal_torque > 0 else 0.0

        if gear_ratio > 0 and tire_radius_cm > 0 and reference_acceleration > 0 and rated_torque > 0:
            supported_weight = (
                rated_torque
                * gear_ratio
                / tire_radius_cm
                * gravity_cm_s2
                / (reference_acceleration * 100.0)
            )
            result.estimated_supported_weight = EstimatedValue(
                value=max(0.0, supported_weight),
                unit="g",
                confidence=model_confidence,
            )
        else:
            # Mandatory UI field: if the model has no torque yet, return a
            # numeric zero rather than replacing the required field with text.
            result.estimated_supported_weight = EstimatedValue(
                value=0.0,
                unit="g",
                confidence=0.0,
            )

        return result
