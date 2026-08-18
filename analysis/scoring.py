"""Final motor performance scoring.

Performance is anchored to HD_PRO=50 by PerformanceAnalysis.  Brush state is
then incorporated as a separate factor; excess torque is not rewarded here.
"""
from __future__ import annotations

from typing import Any

from analysis.models import PerformanceResult, BrushResult, BreakinStrategyResult, ScoreResult


class Scoring:
    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    @staticmethod
    def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
        return max(low, min(high, value))

    def calculate(
        self,
        performance: PerformanceResult,
        brush: BrushResult,
        strategy: BreakinStrategyResult,
    ) -> ScoreResult:
        weights = self.config.get("weights", {})
        performance_weight = float(weights.get("performance", 0.70))
        brush_weight = float(weights.get("brush", 0.30))
        total_weight = max(1e-9, performance_weight + brush_weight)
        performance_weight /= total_weight
        brush_weight /= total_weight

        performance_score = self._clamp(performance.performance_index.value)

        # Brush score: peak itself is ideal (100).  Distance from peak reduces
        # the final index, while unknown/single-sample state remains neutral.
        if brush.peak_offset.value or brush.brush_condition in {"PRE_PEAK", "POST_PEAK"}:
            brush_score = self._clamp(100.0 - abs(brush.peak_offset.value))
        elif brush.brush_condition == "PEAK":
            brush_score = 100.0
        else:
            brush_score = 50.0

        total = performance_score * performance_weight + brush_score * brush_weight
        result = ScoreResult(total_score=round(total, 2), details={
            "performance": round(performance_score, 2),
            "brush": round(brush_score, 2),
            "performance_weight": performance_weight,
            "brush_weight": brush_weight,
            "required_torque_met": None,
        })
        result.rank = self._rank(result.total_score)
        return result

    def _rank(self, score: float) -> str:
        thresholds = self.config.get("rank_thresholds", {})
        if score >= float(thresholds.get("S", 90)):
            return "S"
        if score >= float(thresholds.get("A", 80)):
            return "A"
        if score >= float(thresholds.get("B", 70)):
            return "B"
        if score >= float(thresholds.get("C", 60)):
            return "C"
        return "D"
