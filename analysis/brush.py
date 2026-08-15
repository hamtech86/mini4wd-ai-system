"""Brush-condition estimation for MOTOR_BREAKIN_V3."""
from __future__ import annotations

from typing import Any

from analysis.models import BrushResult, EstimatedValue, FeatureSet


class BrushAnalysis:
    """Estimate brush peak/state on the provisional -10..+10 scale.

    Calibration convention:
      +10 = new
        0 = perfect / brush peak
      -10 = failed

    The current provisional curve uses peak current relative to the configured
    peak threshold.  It is deliberately isolated so later measured data can
    replace the calibration without changing the result contract.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    def analyze(self, features: FeatureSet) -> BrushResult:
        result = BrushResult()
        brush_config = self.config.get("brush", {})
        threshold = float(brush_config.get("peak_current", 2.0))
        threshold = max(threshold, 0.001)

        raw_peak = getattr(features, "brush_peak_current", 0.0) or 0.0
        try:
            peak = max(0.0, float(raw_peak))
        except (TypeError, ValueError):
            peak = 0.0

        # Provisional calibration: threshold current is the perfect/peak point.
        # 0 A maps to +10 (new), 2x threshold maps to -10 (failed).
        score = self._clamp(10.0 - (20.0 * peak / threshold), -10.0, 10.0)
        peak_detected = peak >= threshold

        if peak >= threshold * 2.0:
            condition = "FAILURE"
        elif abs(score) <= 1.0:
            condition = "PEAK"
        elif score > 1.0:
            condition = "NEW"
        else:
            condition = "WORN"

        confidence = 0.85 if peak > 0 else 0.40
        result.peak_detected = peak_detected
        result.brush_condition = condition
        result.confidence = confidence
        result.peak_position = EstimatedValue(
            value=peak,
            unit="A",
            confidence=confidence,
        )
        result.peak_score = EstimatedValue(
            value=score,
            unit="score(-10..+10)",
            confidence=confidence,
        )
        result.explanation = (
            f"Provisional brush score: {score:+.1f} / 10; "
            f"peak current: {peak:.3f} A"
        )
        return result
