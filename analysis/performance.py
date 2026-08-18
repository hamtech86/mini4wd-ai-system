"""Model-based motor performance estimation.

Measurement remains the source of truth.  Motor model data is supplied by the
DB/UI layer and is never hard-coded here.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

from analysis.models import EstimatedValue, FeatureSet, PerformanceResult


class PerformanceAnalysis:
    """Estimate RPM, torque and a provisional supported vehicle weight.

    ``motor_model`` is a DB record (or mapping with the same field names).  If
    it is omitted, the old config fallback is retained for compatibility.
    """

    BENCHMARK_MODEL_ID = "HD_PRO"
    TEST_RPM_VOLTAGE = 3.0

    def __init__(self, config: dict[str, Any]):
        self.config = config

    @staticmethod
    def _number(record: Mapping[str, Any], key: str, default: float = 0.0) -> float:
        try:
            return float(record.get(key, default) or default)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def _legacy(self, features: FeatureSet) -> PerformanceResult:
        performance = self.config.get("performance", {})
        rpm_cfg = performance.get("rpm", {})
        torque_cfg = performance.get("torque", {})
        weight_cfg = performance.get("weight", {})
        voltage = float(features.average_voltage or features.voltage or 0.0)
        current = float(features.average_current or features.current or 0.0)
        rpm = max(0.0, voltage * float(rpm_cfg.get("voltage_gain", 5000.0)))
        torque = max(0.0, current * float(torque_cfg.get("current_gain", 10.0)))
        weight = max(0.0, torque * float(weight_cfg.get("torque_gain", 12.0)))
        return PerformanceResult(
            estimated_no_load_rpm=EstimatedValue(rpm, "rpm", float(rpm_cfg.get("default_confidence", 0.35))),
            estimated_torque=EstimatedValue(torque, "g·cm", float(torque_cfg.get("default_confidence", 0.35))),
            estimated_supported_weight=EstimatedValue(weight, "g", float(weight_cfg.get("default_confidence", 0.30))),
            performance_index=EstimatedValue(0.0, "index", 0.0),
        )

    def analyze(
        self,
        features: FeatureSet,
        motor_model: Mapping[str, Any] | None = None,
        benchmark_model: Mapping[str, Any] | None = None,
    ) -> PerformanceResult:
        if not motor_model:
            return self._legacy(features)

        model = motor_model
        benchmark = benchmark_model or {}
        rpm_nominal = self._number(model, "nominal_rpm")
        current_nominal_ma = self._number(model, "nominal_current_ma")
        torque_nominal = self._number(model, "nominal_torque_gcm")
        voltage = max(0.0, float(features.average_voltage or features.voltage or 0.0))
        current = max(0.0, float(features.average_current or features.current or 0.0))

        # Existing project convention: RPM is estimated from the motor voltage
        # against a 3.0 V reference.  The cap avoids extrapolating indefinitely.
        rpm_cap = float(self.config.get("performance", {}).get("rpm", {}).get("max_voltage_ratio", 1.15))
        rpm_ratio = self._clamp(voltage / self.TEST_RPM_VOLTAGE, 0.0, rpm_cap)
        rpm = rpm_nominal * rpm_ratio

        # Existing project convention: torque is proportional to current /
        # nominal current.  This is explicitly an estimate, not a torque test.
        current_nominal_a = current_nominal_ma / 1000.0
        torque = 0.0 if current_nominal_a <= 0 else torque_nominal * current / current_nominal_a

        benchmark_rpm = self._number(benchmark, "nominal_rpm", 24000.0)
        benchmark_torque = self._number(benchmark, "nominal_torque_gcm", 190.0)
        benchmark_product = max(1e-9, benchmark_rpm * benchmark_torque)
        product_ratio = max(0.0, (rpm * torque) / benchmark_product)

        # Geometric mean prevents either RPM or torque from dominating solely
        # because of units.  The resulting index is anchored at HD-Pro=50.
        performance_ratio = math.sqrt(product_ratio)
        sigma = float(self.config.get("performance", {}).get("index", {}).get("log_sigma", 0.10))
        sigma = max(sigma, 1e-6)
        z = math.log(max(performance_ratio, 1e-9)) / sigma
        index = self._clamp(50.0 + 10.0 * z, 0.0, 100.0)

        weight_gain = float(self.config.get("performance", {}).get("weight", {}).get("torque_gain", 12.0))
        supported_weight = max(0.0, torque * weight_gain)
        confidence = self._clamp(
            0.60 + 0.20 * min(1.0, features.quality) + 0.10 * (1.0 if rpm > 0 else 0.0),
            0.0,
            0.95,
        )

        return PerformanceResult(
            estimated_no_load_rpm=EstimatedValue(rpm, "rpm", confidence),
            estimated_torque=EstimatedValue(torque, "g·cm", confidence),
            estimated_supported_weight=EstimatedValue(supported_weight, "g", confidence * 0.75),
            performance_index=EstimatedValue(index, "index(HD_PRO=50)", confidence * 0.80),
            benchmark_ratio=performance_ratio,
            motor_model_id=str(model.get("motor_model_id", model.get("model_code", ""))),
            motor_model_name=str(model.get("name", "")),
            nominal_rpm=rpm_nominal,
            nominal_current_ma=current_nominal_ma,
            nominal_torque_gcm=torque_nominal,
        )
