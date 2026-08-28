"""Model-based motor performance estimation.

Measurement remains the source of truth. Motor Model data supplies the
canonical scale for estimated motor characteristics; it is never replaced by
an arbitrary current-to-torque multiplier.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

from analysis.models import EstimatedValue, FeatureSet, PerformanceResult


class PerformanceAnalysis:
    """Estimate motor performance from measured features and Motor Model data."""

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
        """Compatibility path only; never use it when a Motor Model is linked."""
        performance = self.config.get("performance", {})
        rpm_cfg = performance.get("rpm", {})
        torque_cfg = performance.get("torque", {})
        voltage = float(features.average_voltage or features.voltage or 0.0)
        rpm = max(0.0, voltage * float(rpm_cfg.get("voltage_gain", 5000.0)))
        # Do not manufacture a torque/weight number from raw current.
        return PerformanceResult(
            estimated_no_load_rpm=EstimatedValue(rpm, "rpm", float(rpm_cfg.get("default_confidence", 0.35))),
            estimated_torque=EstimatedValue(0.0, "g·cm", 0.0),
            estimated_supported_weight=EstimatedValue(0.0, "g", 0.0),
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

        # 3.0 V is the project's comparison reference. The measured voltage
        # normalizes the model RPM without inventing a new motor-specific gain.
        rpm_cap = float(self.config.get("performance", {}).get("rpm", {}).get("max_voltage_ratio", 1.15))
        rpm_ratio = self._clamp(voltage / self.TEST_RPM_VOLTAGE, 0.0, rpm_cap)
        rpm = rpm_nominal * rpm_ratio

        # Torque is a model-estimated characteristic value. A no-load current
        # sample is not a valid torque measurement and must not collapse a
        # 200+ g·cm motor into a sub-1 g·cm result.
        torque = max(0.0, torque_nominal)

        benchmark_rpm = self._number(benchmark, "nominal_rpm", 24000.0)
        benchmark_torque = self._number(benchmark, "nominal_torque_gcm", 190.0)
        benchmark_product = max(1e-9, benchmark_rpm * benchmark_torque)
        product_ratio = max(0.0, (rpm * torque) / benchmark_product)
        performance_ratio = math.sqrt(product_ratio)

        sigma = float(self.config.get("performance", {}).get("index", {}).get("log_sigma", 0.10))
        sigma = max(sigma, 1e-6)
        z = math.log(max(performance_ratio, 1e-9)) / sigma
        index = self._clamp(50.0 + 10.0 * z, 0.0, 100.0)

        # Supported weight is calculated by RequiredTorqueAnalysis in the
        # engine, because it depends on vehicle/course parameters. Do not use
        # a hard-coded torque->weight multiplier here.
        confidence = self._clamp(
            0.65 + 0.20 * min(1.0, features.quality) + 0.10 * (1.0 if rpm > 0 else 0.0),
            0.0,
            0.95,
        )

        return PerformanceResult(
            estimated_no_load_rpm=EstimatedValue(rpm, "rpm", confidence),
            estimated_torque=EstimatedValue(torque, "g·cm", confidence * 0.90),
            estimated_supported_weight=EstimatedValue(0.0, "g", 0.0),
            performance_index=EstimatedValue(index, "index(HD_PRO=50)", confidence * 0.80),
            benchmark_ratio=performance_ratio,
            motor_model_id=str(model.get("motor_model_id", model.get("model_code", ""))),
            motor_model_name=str(model.get("name", "")),
            nominal_rpm=rpm_nominal,
            nominal_current_ma=current_nominal_ma,
            nominal_torque_gcm=torque_nominal,
        )
