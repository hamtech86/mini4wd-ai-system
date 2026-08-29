"""Performance estimation from raw measurements and explicit physical inputs."""
from __future__ import annotations

from typing import Any, Optional

from analysis.models import EstimatedValue, FeatureSet, PerformanceResult


class PerformanceAnalysis:
    """Analyze measured motor performance without hidden vehicle assumptions."""

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

        # RAW measurement-derived values are the analysis source. Motor Model
        # data may supply metadata/nominal reference values, but must not
        # overwrite measured performance.
        measured_rpm = self._measurement_value(features, "rpm", "average_rpm")
        measured_current = self._measurement_value(
            features, "average_current", "current"
        )
        measured_voltage = self._measurement_value(
            features, "motor_voltage", "voltage"
        )

        # Do not invent RPM/current/torque when the raw log does not contain a
        # calibrated measurement. Nominal Motor Model torque is not a measured
        # break-in load torque and therefore is not used for supported weight.
        rpm = max(0.0, measured_rpm or 0.0)
        result.estimated_no_load_rpm = EstimatedValue(
            value=rpm,
            unit="rpm",
            confidence=1.0 if measured_rpm is not None else 0.0,
        )

        result.estimated_torque = EstimatedValue(value=0.0, unit="g·cm", confidence=0.0)
        result.available_torque = EstimatedValue(value=0.0, unit="g·cm", confidence=0.0)
        result.estimated_supported_weight = EstimatedValue(value=0.0, unit="g", confidence=0.0)

        # Supported vehicle weight cannot be derived honestly from no-load
        # break-in current/RPM alone. A future calibrated motor model can fill
        # this result without changing the RAW LOG.
        result.weight_profile = []
        result.weight_suitability = {
            "status": "UNAVAILABLE_UNCALIBRATED",
            "reason": "No calibrated load-performance relationship is available.",
            "gear_ratio": float(reference.get("gear_ratio", 3.5)),
            "tire_diameter_mm": float(reference.get("tire_diameter_mm", 24.0)),
            "course_considered": False,
            "measured_voltage_v": measured_voltage,
            "measured_current_a": measured_current,
            "measured_rpm": measured_rpm,
            "definition_version": "torque-weight-v4-raw-first",
        }
        return result
