"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 analysis/brush.py
=====================================================

Brush Analysis

ブラシ状態解析。

責務
------
・ブラシピーク検出
・ピーク位置推定
・ブラシ状態判定

V1.0では簡易解析。
将来、
電流波形解析、
RPM変化解析、
磁気センサー解析
へ拡張する。
"""

from __future__ import annotations

from typing import Any

from analysis.models import (
    BrushResult,
    FeatureSet,
    EstimatedValue,
)


class BrushAnalysis:
    """
    ブラシ解析
    """

    def __init__(
        self,
        config: dict[str, Any] | None = None,
    ):

        self.config = config or {}


    def analyze(
        self,
        features: FeatureSet,
    ) -> BrushResult:
        """
        FeatureSetからブラシ状態推定
        """

        result = BrushResult()


        #
        # Threshold
        #

        brush_config = self.config.get(
            "brush",
            {},
        )

        peak_current = brush_config.get(
            "peak_current",
            2.0,
        )


        #
        # Peak判定
        #

        if (
            features.average_current
            >= peak_current
        ):

            result.peak_detected = True

            result.brush_condition = (
                "PEAK"
            )

            confidence = 0.60


        else:

            result.peak_detected = False

            result.brush_condition = (
                "NORMAL"
            )

            confidence = 0.40



        #
        # Peak位置
        #

        result.peak_position = EstimatedValue(

            value=features.current_ripple,

            unit="A",

            confidence=confidence,

        )


        result.confidence = confidence


        return result

