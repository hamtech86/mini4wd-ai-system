"""Formatting helpers for break-in analysis results."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any


def _format_score(value: Any) -> str:
    return str(
        Decimal(str(float(value))).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )
    )


def _summary(result: Any) -> str:
    if result is None:
        return "RESULT: --"

    if isinstance(result, list):
        if not result:
            return "RESULT: NO ANALYSIS"
        result = result[-1]

    if not hasattr(result, "performance"):
        return f"RESULT: {result}"

    performance = result.performance
    brush = result.brush
    score = result.score

    rpm = performance.estimated_rpm
    torque = performance.estimated_torque
    weight = performance.estimated_weight

    lines = [
        f"EST RPM: {rpm.value:.0f} rpm  (confidence {rpm.confidence:.2f})",
        f"EST TORQUE: {torque.value:.2f} g·cm",
        f"対応車重: {weight.value:.0f} g",
        f"BRUSH: {brush.brush_condition}  (confidence {brush.confidence:.2f})",
    ]

    total = getattr(score, "total_score", None)
    rank = getattr(score, "rank", None)
    if total is not None and rank:
        lines.append(f"SCORE: {_format_score(total)} / RANK {rank}")

    return "\n".join(lines)


def format_analysis_result(result: Any) -> str:
    """Return a compact, UI-safe break-in analysis summary."""
    return _summary(result)
