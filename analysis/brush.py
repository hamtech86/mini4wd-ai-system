"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 analysis/brush.py
=====================================================

Brush Analysis

ブラシ状態解析。
"""

from __future__ import annotations

from typing import Any

from analysis.models import BrushResult, FeatureSet, EstimatedValue


class BrushAnalysis:
    """ブラシ状態解析。"""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    def analyze(self, features: FeatureSet) -> BrushResult:
        result = BrushResult()
        brush_config = self.config.get("brush", {})
        threshold = float(brush_config.get("peak_current", 2.0))

        measured_peak = getattr(features, "brush_peak_current", 0.0) or 0.0
        try:
            measured_peak = float(measured_peak)
        except (TypeError, ValueError):
            measured_peak = 0.0

        current = max(float(getattr(features, "average_current", 0.0) or 0.0), measured_peak)
        result.peak_detected = current >= threshold
        result.brush_condition = "PEAK" if result.peak_detected else "NORMAL"
        result.confidence = 0.85 if measured_peak > 0 else (0.60 if result.peak_detected else 0.40)

        # Preserve the historical peak_position field while making its value
        # meaningful: it now represents the measured brush peak current in A.
        result.peak_position = EstimatedValue(
            value=measured_peak if measured_peak > 0 else float(getattr(features, "current_ripple", 0.0) or 0.0),
            unit="A",
            confidence=result.confidence,
        )
        result.explanation = (
            f"Measured brush peak current: {measured_peak:.3f} A"
            if measured_peak > 0
            else "No dedicated brush peak value was supplied by the measurement stream."
        )
        return result
