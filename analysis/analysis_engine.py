"""MOTOR_BREAKIN_V3 analysis pipeline.

The engine consumes immutable Measurement data and produces re-runnable
AnalysisResult objects. Database and Arduino access remain outside this layer.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from analysis.config_loader import ConfigLoader
from analysis.validation import Validation
from analysis.feature_extractor import FeatureExtractor
from analysis.performance import PerformanceAnalysis
from analysis.brush import BrushAnalysis
from analysis.breakin_strategy import BreakinStrategy
from analysis.required_torque import RequiredTorqueAnalysis, VehicleSpec
from analysis.scoring import Scoring
from analysis.models import AnalysisResult, FeatureSet, EstimatedValue


class AnalysisEngine:
    """Analysis Engine V2."""

    def __init__(self, config_directory: str = "config"):
        self.loader = ConfigLoader(config_directory)
        analysis_config = self.loader.load("analysis.yaml")
        scoring_config = self.loader.load("scoring.yaml")
        recipe_config = self.loader.load("breakin_recipes.yaml")
        self.validation = Validation(analysis_config)
        self.extractor = FeatureExtractor()
        self.performance = PerformanceAnalysis(analysis_config)
        self.brush = BrushAnalysis(analysis_config)
        self.strategy = BreakinStrategy(recipe_config)
        self.required_torque = RequiredTorqueAnalysis()
        self.scoring = Scoring(scoring_config)
        self.analysis_version = analysis_config.get("analysis_version", "2.0")

    def analyze(
        self,
        measurement,
        *,
        motor_model: Mapping[str, Any] | None = None,
        benchmark_model: Mapping[str, Any] | None = None,
        vehicle_spec: VehicleSpec | Mapping[str, float] | None = None,
    ) -> AnalysisResult:
        validation = self.validation.validate(measurement)
        features = self.extractor.extract(measurement)
        performance = self.performance.analyze(
            features, motor_model=motor_model, benchmark_model=benchmark_model
        )
        brush = self.brush.analyze(features)
        strategy = self.strategy.analyze(features)
        score = self.scoring.calculate(performance, brush, strategy)
        self._apply_vehicle_requirement(score, performance, vehicle_spec)
        return self._result(validation, performance, brush, strategy, score)

    def analyze_series(
        self,
        measurements: Iterable,
        *,
        motor_model: Mapping[str, Any] | None = None,
        benchmark_model: Mapping[str, Any] | None = None,
        vehicle_spec: VehicleSpec | Mapping[str, float] | None = None,
    ) -> AnalysisResult:
        items = list(measurements)
        if not items:
            return AnalysisResult(
                analysis_version=self.analysis_version,
                analysis_datetime=datetime.now(timezone.utc).isoformat(),
                confidence=0.0,
            )

        result = self.analyze(
            items[-1], motor_model=motor_model, benchmark_model=benchmark_model,
            vehicle_spec=vehicle_spec,
        )
        features: list[FeatureSet] = [self.extractor.extract(item) for item in items]
        result.brush = self.brush.analyze_series(features)
        result.score = self.scoring.calculate(result.performance, result.brush, result.strategy)
        self._apply_vehicle_requirement(result.score, result.performance, vehicle_spec)
        result.confidence = min(result.confidence or 1.0, result.brush.confidence or 1.0)
        return result

    def _supported_weight(self, motor_torque_gcm: float) -> float:
        """Return the maximum supported standard weight, 115-155 g in 5 g steps."""
        torque = max(0.0, float(motor_torque_gcm))
        supported = 0.0
        for weight_g in range(115, 156, 5):
            requirement = self.required_torque.calculate(VehicleSpec(weight_g=weight_g))
            if torque >= requirement.required_torque_gcm.value:
                supported = float(weight_g)
        return supported

    def _apply_vehicle_requirement(self, score, performance, vehicle_spec) -> None:
        # Always expose the model-based supported-weight estimate when a motor
        # model is linked. It is derived from the physics model, not torque*12.
        if performance.nominal_torque_gcm > 0:
            supported = self._supported_weight(performance.estimated_torque.value)
            performance.estimated_supported_weight = EstimatedValue(
                supported, "g", performance.estimated_torque.confidence * 0.85
            )
            score.details["estimated_supported_weight_g"] = supported
        else:
            score.details["estimated_supported_weight_g"] = None

        if vehicle_spec is None:
            score.details["required_torque_met"] = None
            return
        requirement = self.required_torque.calculate(vehicle_spec)
        margin, margin_percent = self.required_torque.margin(
            performance.estimated_torque.value, requirement.required_torque_gcm.value
        )
        score.details.update({
            "required_torque_gcm": requirement.required_torque_gcm.value,
            "torque_margin_gcm": margin,
            "torque_margin_percent": margin_percent,
            "traction_limited": requirement.traction_limited,
            "required_torque_met": margin >= 0,
        })
        if margin < 0:
            score.total_score = min(score.total_score, 49.0)
            score.rank = "D"

    def _result(self, validation, performance, brush, strategy, score) -> AnalysisResult:
        return AnalysisResult(
            validation=validation,
            performance=performance,
            brush=brush,
            strategy=strategy,
            score=score,
            analysis_version=self.analysis_version,
            analysis_datetime=datetime.now(timezone.utc).isoformat(),
            confidence=min(
                validation.quality_score or 1.0,
                performance.performance_index.confidence or 1.0,
                brush.confidence or 1.0,
            ),
        )
