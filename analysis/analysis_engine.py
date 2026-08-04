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

from typing import Any

from analysis.config_loader import ConfigLoader

from analysis.validation import Validation
from analysis.feature_extractor import FeatureExtractor
from analysis.performance import PerformanceAnalysis
from analysis.brush import BrushAnalysis
from analysis.breakin_strategy import BreakinStrategy
from analysis.scoring import Scoring

from analysis.models import (
    AnalysisResult,
)


class AnalysisEngine:
    """
    Analysis Engine V1.1
    """

    def __init__(
        self,
        config_directory: str = "config",
    ):

        #
        # Config管理
        #

        self.loader = ConfigLoader(
            config_directory
        )


        #
        # Config Load
        #

        analysis_config = (
            self.loader.load(
                "analysis.yaml"
            )
        )

        scoring_config = (
            self.loader.load(
                "scoring.yaml"
            )
        )

        recipe_config = (
            self.loader.load(
                "breakin_recipes.yaml"
            )
        )


        #
        # Module生成
        #

        self.validation = Validation(
            analysis_config
        )


        self.extractor = FeatureExtractor()


        self.performance = (
            PerformanceAnalysis(
                analysis_config
            )
        )


        self.brush = BrushAnalysis(
            analysis_config
        )


        self.strategy = (
            BreakinStrategy(
                recipe_config
            )
        )


        self.scoring = Scoring(
            scoring_config
        )


        #
        # Version
        #

        self.analysis_version = (
            analysis_config.get(
                "analysis_version",
                "1.0",
            )
        )


    def analyze(
        self,
        measurement,
    ) -> AnalysisResult:
        """
        Measurement解析
        """


        #
        # Validation
        #

        validation = (
            self.validation.validate(
                measurement
            )
        )


        #
        # Feature Extract
        #

        features = (
            self.extractor.extract(
                measurement
            )
        )


        #
        # Performance
        #

        performance = (
            self.performance.analyze(
                features
            )
        )


        #
        # Brush
        #

        brush = (
            self.brush.analyze(
                features
            )
        )


        #
        # Strategy
        #

        strategy = (
            self.strategy.analyze(
                features
            )
        )


        #
        # Score
        #

        score = (
            self.scoring.calculate(
                performance,
                brush,
                strategy,
            )
        )


        #
        # Result
        #

        result = AnalysisResult()


        result.analysis_version = (
            self.analysis_version
        )

        result.validation = validation

        result.performance = performance

        result.brush = brush

        result.strategy = strategy

        result.score = score


        return result


