"""Formatting helpers for break-in analysis results."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any


def _format_score(value: Any) -> str:
    """Format a score to one decimal place using conventional half-up rounding."""
    return str(
        Decimal(str(float(value))).quantize(
            Decimal("0.1"), rounding=ROUND_HALF_UP
        )
    )


def format_analysis_result(result: Any) -> str:
    """Return a compact, UI-safe summary for an AnalysisEngine result."""
    if result is None:
        return "RESULT: --"

    if isinstance(result, list):
        if not result:
            return "RESULT: NO ANALYSIS"

        latest = result[-1]
        if hasattr(latest, "score"):
            score = getattr(latest, "score")
            total = getattr(score, "total_score", None)
            rank = getattr(score, "rank", None)
            if total is not None and rank:
                return f"RESULT: SCORE {_format_score(total)} / RANK {rank} ({len(result)} samples)"

        if isinstance(latest, dict):
            score = latest.get("score")
            if isinstance(score, dict):
                total = score.get("total_score", score.get("score"))
                rank = score.get("rank")
                if total is not None and rank:
                    return f"RESULT: SCORE {_format_score(total)} / RANK {rank} ({len(result)} samples)"

            summary = latest.get("summary") or latest.get("result")
            if summary is not None:
                return f"RESULT: {summary} ({len(result)} samples)"

        return f"RESULT: {len(result)} ANALYSIS RESULT(S)"

    if hasattr(result, "score"):
        score = getattr(result, "score")
        total = getattr(score, "total_score", None)
        rank = getattr(score, "rank", None)
        if total is not None and rank:
            return f"RESULT: SCORE {_format_score(total)} / RANK {rank}"

    if isinstance(result, dict):
        summary = result.get("summary") or result.get("result") or result.get("score")
        if summary is not None:
            return f"RESULT: {summary}"

    return f"RESULT: {result}"
