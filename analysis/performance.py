"""Motor performance analysis and vehicle-weight suitability."""

from __future__ import annotations

from typing import Any, Optional

from analysis.models import EstimatedValue, FeatureSet, PerformanceResult
from analysis.weight_suitability import WeightSuitabilityAnalysis


class PerformanceAnalysis:
    """Estimate motor performance from measurements plus Motor Model data."""

    GRAVITY_MPS2 = 9.80665
    GCM_TO_NM = 9.80665e-5

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

    def _required_torque_gcm(self, weight_g: float, reference: dict[str, Any]) -> float:
        """Calculate required motor torque for the fixed reference vehicle."""
        mass_kg = max(0.0, float(weight_g)) / 1000.0
        acceleration = max(0.0, float(reference.get("reference_acceleration_mps2", 3.0)))
        efficiency = float(reference.get("drivetrain_efficiency", 0.75))
        efficiency = max(1e-9, min(1.0, efficiency))
        gear_ratio = max(0.0, float(reference.get("gear_ratio", 3.5)))
        radius_m = max(0.0, float(reference.get("tire_diameter_mm", 24.0))) / 2000.0
        if mass_kg <= 0 or acceleration <= 0 or gear_ratio <= 0 or radius_m <= 0:
            return 0.0
        wheel_force_n = mass_kg * acceleration / efficiency
        motor_torque_nm = wheel_force_n * radius_m / gear_ratio
        return motor_torque_nm / self.GCM_TO_NM

    def analyze(
        self,
        features: FeatureSet,
        motor_model: Optional[dict[str, Any]] = None,
    ) -> PerformanceResult:
        result = PerformanceResult()
        performance = self.config.get("performance", {})
        reference = performance.get("reference_vehicle", {})
        weight_cfg = performance.get("weight", {})

        current = abs(float(features.average_current or features.current or 0.0))

        # Measured RPM has priority. Motor Model nominal RPM is the fallback;
        # voltage is never converted directly into RPM.
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
            value=rpm, unit="rpm", confidence=rpm_confidence
        )

        # Individual operating-point torque is provisional: Motor Model supplies
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
            estimated_torque = 0.0
            torque_confidence = 0.0

        result.estimated_torque = EstimatedValue(
            value=estimated_torque, unit="g·cm", confidence=torque_confidence
        )

        # A break-in current sample is not a calibrated maximum-load point.
        # Therefore supported weight is based on the Motor Model capability,
        # not on the low-PWM break-in current.
        available_torque = max(0.0, nominal_torque or 0.0)
        result.available_torque = EstimatedValue(
            value=available_torque,
            unit="g·cm",
            confidence=model_confidence if available_torque > 0 else 0.0,
        )

        reference_weight = float(reference.get(
            "reference_weight_g", weight_cfg.get("reference_weight_g", 130.0)
        ))
        required_130 = self._required_torque_gcm(reference_weight, reference)
        result.required_torque_130g = EstimatedValue(
            value=required_130,
            unit="g·cm",
            confidence=1.0 if required_130 > 0 else 0.0,
        )
        margin_130 = available_torque / required_130 if required_130 > 0 else 0.0
        result.torque_margin_130g = EstimatedValue(
            value=max(0.0, margin_130),
            unit="ratio",
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

        # Mandatory numeric UI field: expose the highest weight classified as
        # usable by the configured suitability contract. Zero means no point in
        # the configured profile is supported; it is never omitted.
        result.estimated_supported_weight = EstimatedValue(
            value=suitability.upper_limit_g,
            unit="g",
            confidence=suitability.confidence if available_torque > 0 else 0.0,
        )
        return result
