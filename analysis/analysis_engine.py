"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 analysis/analysis_engine.py
=====================================================

Analysis Engine

解析パイプライン制御。

責務
------
・各解析Module呼び出し
・Config管理
・AnalysisResult生成

禁止
------
・Databaseアクセス
・Arduino通信
・Measurement変更

"""

from __future__ import annotations

from typing import Any, Optional

from analysis.config_loader import ConfigLoader
from analysis.validation import Validation
from analysis.feature_extractor import FeatureExtractor
from analysis.performance import PerformanceAnalysis
from analysis.brush import BrushAnalysis
from analysis.breakin_strategy import BreakinStrategy
from analysis.scoring import Scoring
from analysis.models import AnalysisResult


class AnalysisEngine:
    """Analysis Engine V1.2."""

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
        self.scoring = Scoring(scoring_config)
        self.analysis_version = analysis_config.get("analysis_version", "1.0")

    def analyze(
        self,
        measurement,
        motor_model: Optional[dict[str, Any]] = None,
    ) -> AnalysisResult:
        """Measurement解析。

        ``motor_model`` is supplied by the application/controller layer.
        The Analysis layer itself never accesses the database.
        """
        validation = self.validation.validate(measurement)
        features = self.extractor.extract(measurement)
        performance = self.performance.analyze(features, motor_model=motor_model)
        brush = self.brush.analyze(features)
        strategy = self.strategy.analyze(features)
        score = self.scoring.calculate(performance, brush, strategy)

        result = AnalysisResult()
        result.analysis_version = self.analysis_version
        result.validation = validation
        result.performance = performance
        result.brush = brush
        result.strategy = strategy
        result.score = score
        return result
