"""Performance estimation from measured data and Motor Model master data."""
from __future__ import annotations

from typing import Any, Optional

from analysis.models import EstimatedValue, FeatureSet, PerformanceResult


class PerformanceAnalysis:
    """Estimate motor performance using measured data and Motor Model master data."""

    GRAVITY_MPS2 = 9.80665
    GCM_TO_NM = 9.80665e-5

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

    def _required_torque_gcm(self, weight_g: float, reference: dict[str, Any]) -> float:
        """Required motor torque for the configured reference acceleration.

        Gear ratio and tire diameter are physical inputs. Acceleration and
        drivetrain efficiency are explicit model assumptions, not a hidden
        vehicle/course value.
        """
        mass_kg = max(0.0, float(weight_g)) / 1000.0
        acceleration = max(0.0, float(reference.get("reference_acceleration_mps2", 20.0)))
        efficiency = max(1e-9, min(1.0, float(reference.get("drivetrain_efficiency", 0.75))))
        gear_ratio = max(0.0, float(reference.get("gear_ratio", 3.5)))
        radius_m = max(0.0, float(reference.get("tire_diameter_mm", 24.0))) / 2000.0
        if mass_kg <= 0 or acceleration <= 0 or gear_ratio <= 0 or radius_m <= 0:
            return 0.0

        wheel_force_n = mass_kg * acceleration / efficiency
        motor_torque_nm = wheel_force_n * radius_m / gear_ratio
        return motor_torque_nm / self.GCM_TO_NM

    def _weight_from_torque_g(self, torque_gcm: float, reference: dict[str, Any]) -> float:
        """Continuous torque-equivalent vehicle weight in grams.

        This is a model estimate, not a claim of race-proven supported weight.
        No fixed 130 g value is injected into the calculation.
        """
        torque_per_gram = self._required_torque_gcm(1.0, reference)
        if torque_per_gram <= 0 or torque_gcm <= 0:
            return 0.0
        return torque_gcm / torque_per_gram

    def analyze(
        self,
        features: FeatureSet,
        motor_model: Optional[dict[str, Any]] = None,
    ) -> PerformanceResult:
        result = PerformanceResult()
        performance = self.config["performance"]
        reference = performance.get("reference_vehicle", {})
        weight_config = performance.get("weight", {})

        # Break-in current is diagnostic input only. It is not a calibrated
        # load-torque measurement and must not be converted directly to torque.
        current = abs(float(features.average_current or features.current or 0.0))
        _ = current

        measured_rpm = float(features.rpm or 0.0)
        model_rpm = self._model_value(motor_model, "nominal_rpm")
        model_confidence = self._confidence(
            self._model_value(motor_model, "data_confidence"), 0.0
        )
        rpm = model_rpm if model_rpm is not None and model_rpm > 0 else measured_rpm
        rpm_confidence = model_confidence if model_rpm is not None and model_rpm > 0 else 0.0
        result.estimated_no_load_rpm = EstimatedValue(
            value=max(0.0, rpm), unit="rpm", confidence=rpm_confidence
        )

        # Current torque baseline remains the Motor Model nominal torque until
        # a calibrated load-torque measurement is available.
        nominal_torque = self._model_value(motor_model, "nominal_torque_gcm")
        available_torque = max(0.0, nominal_torque or 0.0)
        torque_confidence = model_confidence if available_torque > 0 else 0.0
        result.estimated_torque = EstimatedValue(
            value=available_torque, unit="g·cm", confidence=torque_confidence
        )
        result.available_torque = EstimatedValue(
            value=available_torque, unit="g·cm", confidence=torque_confidence
        )

        # IMPORTANT: there is no hidden 130 g reference anymore. The
        # torque-equivalent weight is calculated continuously from the supplied
        # torque and the explicit physical/model assumptions.
        estimated_weight = self._weight_from_torque_g(available_torque, reference)
        result.estimated_supported_weight = EstimatedValue(
            value=estimated_weight,
            unit="g",
            confidence=torque_confidence,
        )

        raw_profile = weight_config.get(
            "weight_profile_g",
            [100, 110, 120, 130, 140, 150, 160, 170, 180],
        )
        try:
            weights = sorted({float(w) for w in raw_profile if float(w) > 0})
        except (TypeError, ValueError):
            weights = [100.0, 110.0, 120.0, 130.0, 140.0, 150.0, 160.0, 170.0, 180.0]

        recommended_threshold = float(weight_config.get("recommended_margin", 1.30))
        acceptable_threshold = float(weight_config.get("acceptable_margin", 1.10))
        limit_threshold = float(weight_config.get("limit_margin", 1.00))

        profile = []
        recommended_max = 0.0
        acceptable_max = 0.0
        upper_limit = 0.0

        for weight_g in weights:
            required = self._required_torque_gcm(weight_g, reference)
            margin = available_torque / required if required > 0 else 0.0
            if margin >= recommended_threshold:
                status = "RECOMMENDED"
                recommended_max = weight_g
            elif margin >= acceptable_threshold:
                status = "ACCEPTABLE"
                acceptable_max = weight_g
            elif margin >= limit_threshold:
                status = "LIMIT"
                upper_limit = weight_g
            else:
                status = "UNSUITABLE"

            profile.append({
                "weight_g": weight_g,
                "required_torque_gcm": required,
                "available_torque_gcm": available_torque,
                "surplus_torque_gcm": max(0.0, available_torque - required),
                "torque_margin": max(0.0, margin),
                "supported": 1.0 if margin >= limit_threshold else 0.0,
                "status": status,
            })

        if acceptable_max == 0.0:
            acceptable_max = recommended_max
        if upper_limit == 0.0:
            upper_limit = acceptable_max

        result.weight_profile = profile
        result.weight_suitability = {
            "estimated_torque_equivalent_weight_g": estimated_weight,
            "recommended_min_g": min(
                [p["weight_g"] for p in profile if p["status"] == "RECOMMENDED"],
                default=0.0,
            ),
            "recommended_max_g": recommended_max,
            "upper_limit_g": upper_limit,
            "acceptable_max_g": acceptable_max,
            "target_acceleration_mps2": float(reference.get("reference_acceleration_mps2", 20.0)),
            "drivetrain_efficiency": float(reference.get("drivetrain_efficiency", 0.75)),
            "tire_diameter_mm": float(reference.get("tire_diameter_mm", 24.0)),
            "gear_ratio": float(reference.get("gear_ratio", 3.5)),
            "available_torque_gcm": available_torque,
            "points": profile,
            "definition_version": "torque-weight-v3",
        }
        return result
