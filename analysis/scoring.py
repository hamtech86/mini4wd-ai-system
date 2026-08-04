"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 analysis/scoring.py
=====================================================

Scoring

Analysis結果を評価スコアへ変換する。

責務
------
・性能評価
・安定性評価
・総合ランク生成

係数・閾値は設定ファイル管理。
"""

from __future__ import annotations

from typing import Any

from analysis.models import (
    PerformanceResult,
    BrushResult,
    BreakinStrategyResult,
    ScoreResult,
)


class Scoring:
    """
    Score Calculator
    """

    def __init__(
        self,
        config: dict[str, Any] | None = None,
    ):

        self.config = config or {}


    def calculate(
        self,
        performance: PerformanceResult,
        brush: BrushResult,
        strategy: BreakinStrategyResult,
    ) -> ScoreResult:
        """
        総合評価計算
        """

        result = ScoreResult()


        #
        # 設定取得
        #

        weights = self.config.get(
            "weights",
            {},
        )

        thresholds = self.config.get(
            "rank_thresholds",
            {},
        )


        #
        # Performance Score
        #

        rpm_score = self._normalize(
            performance.estimated_rpm.value,
            30000,
        )


        torque_score = self._normalize(
            performance.estimated_torque.value,
            100,
        )


        stability_score = (
            1.0
            if brush.peak_detected is False
            else 0.7
        )


        #
        # Weight
        #

        speed_weight = weights.get(
            "speed",
            0.4,
        )

        torque_weight = weights.get(
            "torque",
            0.4,
        )

        stability_weight = weights.get(
            "stability",
            0.2,
        )


        total = (

            rpm_score
            * speed_weight

            +

            torque_score
            * torque_weight

            +

            stability_score
            * stability_weight

        )


        result.total_score = (
            total * 100
        )


        #
        # Rank
        #

        result.rank = self._rank(
            result.total_score,
            thresholds,
        )


        #
        # Detail
        #

        result.details = {

            "speed":
                rpm_score * 100,

            "torque":
                torque_score * 100,

            "stability":
                stability_score * 100,

        }


        return result


    def _normalize(
        self,
        value: float,
        maximum: float,
    ) -> float:
        """
        0～1へ正規化
        """

        if maximum <= 0:

            return 0.0

        return max(
            0.0,
            min(
                value / maximum,
                1.0,
            ),
        )


    def _rank(
        self,
        score: float,
        thresholds: dict,
    ) -> str:

        if score >= thresholds.get(
            "S",
            90,
        ):

            return "S"


        if score >= thresholds.get(
            "A",
            80,
        ):

            return "A"


        if score >= thresholds.get(
            "B",
            70,
        ):

            return "B"


        if score >= thresholds.get(
            "C",
            60,
        ):

            return "C"


        return "D"

