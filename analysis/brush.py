"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 analysis/brush.py
=====================================================

Brush Analysis

Estimate brush/contact condition from measured current level and
short-window current ripple. KY-024 RPM is not used.
=====================================================
"""

from __future__ import annotations

from typing import Any

from analysis.models import BrushResult, EstimatedValue, FeatureSet


class BrushAnalysis:
    """Electrical brush/contact condition estimator."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}

    def analyze(self, features: FeatureSet) -> BrushResult:
        result = BrushResult()

        current = max(0.0, float(getattr(features, "average_current", 0.0)))
        ripple = max(0.0, float(getattr(features, "current_ripple", 0.0)))
        peak = max(0.0, float(getattr(features, "brush_peak_current", 0.0)))

        # Ripple ratio is more useful than an absolute threshold because the
        # motor current changes substantially between break-in phases.
        ripple_ratio = ripple / max(current, 0.05)

        if current <= 0.05:
            condition = "NO_LOAD"
            confidence = 0.25
        elif ripple_ratio >= 0.75:
            condition = "BREAK_IN_ACTIVE"
            confidence = 0.65
        elif ripple_ratio >= 0.40:
            condition = "TRANSITION"
            confidence = 0.60
        elif ripple_ratio >= 0.20:
            condition = "STABILIZING"
            confidence = 0.70
        else:
            condition = "STABLE"
            confidence = 0.75

        result.peak_detected = peak > current * 1.25 if current > 0.05 else False
        result.brush_condition = condition
        result.peak_position = EstimatedValue(
            value=ripple,
            unit="A",
            confidence=confidence,
        )
        result.confidence = confidence
        result.explanation = (
            f"current={current:.3f}A, ripple={ripple:.3f}A, "
            f"ripple_ratio={ripple_ratio:.2f}"
        )
        return result
