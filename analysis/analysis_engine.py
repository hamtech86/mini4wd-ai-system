"""MOTOR_BREAKIN_V3 analysis pipeline.

The engine consumes immutable Measurement data and produces re-runnable
AnalysisResult objects.  Database and Arduino access remain outside this layer.
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
from analysis.models import AnalysisResult, FeatureSet


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
        """Analyze one Measurement without modifying it.

        ``motor_model`` and ``benchmark_model`` must come from the DB layer.
        ``vehicle_spec`` is optional; when supplied, required torque and motor
        torque margin are added to the result score details.
        """
        validation = self.validation.validate(measurement)
        features = self.extractor.extract(measurement)
        performance = self.performance.analyze(
            features,
            motor_model=motor_model,
            benchmark_model=benchmark_model,
        )
        brush = self.brush.analyze(features)
        strategy = self.strategy.analyze(features)
        score = self.scoring.calculate(performance, brush, strategy)

        if vehicle_spec is not None:
            requirement = self.required_torque.calculate(vehicle_spec)
            margin, margin_percent = self.required_torque.margin(
                performance.estimated_torque.value,
                requirement.required_torque_gcm.value,
            )
            requirement.margin_gcm = margin
            requirement.margin_percent = margin_percent
            score.details["required_torque_gcm"] = requirement.required_torque_gcm.value
            score.details["torque_margin_gcm"] = margin
            score.details["torque_margin_percent"] = margin_percent
            score.details["traction_limited"] = requirement.traction_limited

            # Failing the minimum torque requirement is a hard suitability fail;
            # surplus torque receives no extra score.
            if margin < 0:
                score.details["required_torque_met"] = False
                score.total_score = min(score.total_score, 49.0)
            else:
                score.details["required_torque_met"] = True
        else:
            score.details["required_torque_met"] = None

        result = AnalysisResult(
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
        return result

    def analyze_series(
        self,
        measurements: Iterable,
        *,
        motor_model: Mapping[str, Any] | None = None,
        benchmark_model: Mapping[str, Any] | None = None,
        vehicle_spec: VehicleSpec | Mapping[str, float] | None = None,
    ) -> AnalysisResult:
        """Analyze a session and use the complete history for brush peak state."""
        items = list(measurements)
        if not items:
            return AnalysisResult(
                analysis_version=self.analysis_version,
                analysis_datetime=datetime.now(timezone.utc).isoformat(),
                confidence=0.0,
            )

        result = self.analyze(
            items[-1],
            motor_model=motor_model,
            benchmark_model=benchmark_model,
            vehicle_spec=vehicle_spec,
        )
        features: list[FeatureSet] = [self.extractor.extract(item) for item in items]
        result.brush = self.brush.analyze_series(features)
        result.score = self.scoring.calculate(
            result.performance,
            result.brush,
            result.strategy,
        )
        return result
