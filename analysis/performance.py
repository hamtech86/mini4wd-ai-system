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
        """Required motor torque for the fixed race-reference vehicle conditions."""
        mass_kg = max(0.0, float(weight_g)) / 1000.0
        acceleration = max(
            0.0, float(reference.get("reference_acceleration_mps2", 20.0))
        )
        efficiency = float(reference.get("drivetrain_efficiency", 0.75))
        efficiency = max(1e-9, min(1.0, efficiency))
        gear_ratio = max(0.0, float(reference.get("gear_ratio", 3.5)))
        radius_m = max(0.0, float(reference.get("tire_diameter_mm", 24.0))) / 2000.0
        if mass_kg <= 0 or acceleration <= 0 or gear_ratio <= 0 or radius_m <= 0:
            return 0.0

        # Vehicle force required for the reference acceleration, corrected for
        # drivetrain losses, then converted through the gear ratio to motor torque.
        wheel_force_n = mass_kg * acceleration / efficiency
        motor_torque_nm = wheel_force_n * radius_m / gear_ratio
        return motor_torque_nm / self.GCM_TO_NM

    def analyze(
        self,
        features: FeatureSet,
        motor_model: Optional[dict[str, Any]] = None,
    ) -> PerformanceResult:
        result = PerformanceResult()
        performance = self.config["performance"]
        reference = performance.get("reference_vehicle", {})
        weight_config = performance.get("weight", {})

        # Measured current is an electrical/brush diagnostic input. It is NOT
        # converted directly into torque: break-in current is not a calibrated
        # load-torque measurement and doing so produced false 5 g-class results.
        current = abs(float(features.average_current or features.current or 0.0))
        _ = current

        # KY-024/measured RPM is retained as a reference observation. It is not
        # treated as the formal no-load RPM. The formal estimate falls back to
        # the Motor Model nominal RPM until a calibrated RPM measurement exists.
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

        # Torque definition (current revision):
        # Estimated/Available Motor Torque is the Motor Model nominal torque.
        # The measured break-in current is NOT multiplied by nominal torque /
        # nominal current because nominal current is not a calibrated stall/load
        # current. This keeps torque in a physically meaningful g·cm range.
        nominal_torque = self._model_value(motor_model, "nominal_torque_gcm")
        available_torque = max(0.0, nominal_torque or 0.0)
        torque_confidence = model_confidence if available_torque > 0 else 0.0
        result.estimated_torque = EstimatedValue(
            value=available_torque, unit="g·cm", confidence=torque_confidence
        )
        result.available_torque = EstimatedValue(
            value=available_torque,
            unit="g·cm",
            confidence=torque_confidence,
        )

        reference_weight = float(reference.get("reference_weight_g", 130.0))
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
            confidence=torque_confidence,
        )

        raw_profile = weight_config.get(
            "weight_profile_g",
            reference.get(
                "weight_profile_g",
                [115, 120, 125, 130, 135, 140, 145, 150, 155],
            ),
        )
        try:
            weights = sorted({float(w) for w in raw_profile if float(w) > 0})
        except (TypeError, ValueError):
            weights = [115.0, 120.0, 125.0, 130.0, 135.0, 140.0, 145.0, 150.0, 155.0]

        # Margin bands are intentionally explicit so the result is useful for
        # race setup rather than merely saying that a weight is mathematically possible.
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

        # Highest weight in the configured profile that remains within the
        # minimum physical limit. This is the legacy-compatible supported weight.
        supported_weights = [p["weight_g"] for p in profile if p["supported"] > 0]
        supported_weight = max(supported_weights) if supported_weights else 0.0

        result.weight_profile = profile
        result.estimated_supported_weight = EstimatedValue(
            value=supported_weight,
            unit="g",
            confidence=torque_confidence,
        )

        # Stable UI/API contract. UI does not calculate suitability itself.
        result.weight_suitability = {
            "recommended_min_g": min(
                [p["weight_g"] for p in profile if p["status"] == "RECOMMENDED"],
                default=0.0,
            ),
            "recommended_max_g": recommended_max,
            "upper_limit_g": upper_limit,
            "acceptable_max_g": acceptable_max,
            "current_reference_g": reference_weight,
            "comparison_weight_g": float(reference.get("comparison_weight_g", 140.0)),
            "target_acceleration_mps2": float(reference.get("reference_acceleration_mps2", 20.0)),
            "drivetrain_efficiency": float(reference.get("drivetrain_efficiency", 0.75)),
            "tire_diameter_mm": float(reference.get("tire_diameter_mm", 24.0)),
            "gear_ratio": float(reference.get("gear_ratio", 3.5)),
            "available_torque_gcm": available_torque,
            "required_torque_130g": required_130,
            "torque_margin_130g": margin_130,
            "points": profile,
            "definition_version": "torque-weight-v2",
        }
        return result
