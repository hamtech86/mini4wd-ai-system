"""Brush peak / break-in trajectory analysis."""
from __future__ import annotations

from typing import Any, Iterable

from analysis.models import BrushResult, EstimatedValue, FeatureSet


class BrushAnalysis:
    """Estimate brush state from ACS2/brush-current history.

    Convention requested by the project:
      + value = before the brush peak
        0 value = brush peak / best point
      - value = after the brush peak

    The trajectory calculation is intentionally separate from the single-sample
    analysis so it can be re-run from immutable Measurement history.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    @staticmethod
    def _clamp(value: float, low: float, high: float) -> float:
        return max(low, min(high, value))

    @staticmethod
    def _peak_values(features: Iterable[FeatureSet]) -> list[float]:
        values: list[float] = []
        for feature in features:
            try:
                value = float(getattr(feature, "brush_peak_current", 0.0) or 0.0)
            except (TypeError, ValueError):
                value = 0.0
            values.append(max(0.0, value))
        return values

    def analyze(self, features: FeatureSet) -> BrushResult:
        """Analyze one sample without inventing a peak history."""
        result = BrushResult()
        peak = max(0.0, float(getattr(features, "brush_peak_current", 0.0) or 0.0))
        threshold = max(0.001, float(self.config.get("brush", {}).get("peak_current", 2.0)))
        confidence = 0.45 if peak <= 0 else 0.60

        # A single sample cannot establish before/after peak position.  It is
        # therefore reported as unknown rather than falsely claiming a life stage.
        result.peak_position = EstimatedValue(peak, "A", confidence)
        result.peak_score = EstimatedValue(0.0, "peak_offset(-100..+100)", 0.20)
        result.peak_detected = peak >= threshold
        result.brush_condition = "OBSERVATION_ONLY"
        result.confidence = confidence
        result.explanation = "Peak position requires a measurement series."
        return result

    def analyze_series(self, features: Iterable[FeatureSet]) -> BrushResult:
        values = self._peak_values(features)
        result = BrushResult()
        if not values:
            result.explanation = "No brush-current samples."
            return result

        peak = max(values)
        peak_index = values.index(peak)
        current_index = len(values) - 1
        start = values[0]
        threshold = max(0.001, float(self.config.get("brush", {}).get("peak_current", 2.0)))

        if current_index <= peak_index:
            denom = max(1, peak_index)
            offset = 100.0 * (peak_index - current_index) / denom
            before_after = "BEFORE_PEAK" if current_index < peak_index else "PEAK"
        else:
            denom = max(1, len(values) - 1 - peak_index)
            offset = -100.0 * (current_index - peak_index) / denom
            before_after = "AFTER_PEAK"

        growth = 0.0 if start <= 0 else (peak - start) / start * 100.0
        peak_detected = peak >= threshold
        # Keep the requested convention: 0 at peak, + before, - after.
        confidence = self._clamp(0.55 + min(0.35, len(values) / 100.0), 0.0, 0.90)

        if before_after == "PEAK":
            condition = "PEAK"
        elif before_after == "AFTER_PEAK":
            condition = "POST_PEAK"
        else:
            condition = "PRE_PEAK"

        result.peak_detected = peak_detected
        result.peak_position = EstimatedValue(peak, "A", confidence)
        result.peak_score = EstimatedValue(offset, "peak_offset(-100..+100)", confidence)
        result.peak_offset = EstimatedValue(offset, "peak_offset(-100..+100)", confidence)
        result.growth_rate_percent = growth
        result.life_position_percent = offset
        result.brush_condition = condition
        result.confidence = confidence
        result.explanation = (
            f"Peak={peak:.3f} A at sample {peak_index}; "
            f"current offset={offset:+.1f}; growth={growth:+.1f}%"
        )
        return result
