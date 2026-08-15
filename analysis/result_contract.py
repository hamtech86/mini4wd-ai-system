"""Result presentation contract for MOTOR_BREAKIN_V3.

The UI consumes this small adapter instead of interpreting AnalysisResult
internals. It keeps the four provisional estimates explicit and labeled as
estimates.
"""
from __future__ import annotations

from typing import Any


def _value(obj: Any, default: str = "--") -> str:
    value = getattr(obj, "value", None)
    if value is None:
        return default
    return str(value)


def build_estimated_result(analysis_result: Any) -> dict[str, str]:
    """Return the four required provisional estimate display values."""
    performance = getattr(analysis_result, "performance", None)
    brush = getattr(analysis_result, "brush", None)
    if performance is None:
        return {
            "estimated_no_load_rpm": "--",
            "estimated_torque": "--",
            "brush_peak_score": "--",
            "estimated_supported_weight": "--",
        }

    rpm = getattr(performance, "estimated_no_load_rpm", None)
    torque = getattr(performance, "estimated_torque", None)
    weight = getattr(performance, "estimated_supported_weight", None)
    score = getattr(brush, "peak_score", None)

    return {
        "estimated_no_load_rpm": f"{_value(rpm)} rpm" if rpm else "--",
        "estimated_torque": f"{_value(torque)} g·cm" if torque else "--",
        "brush_peak_score": f"{_value(score)} / 10" if score else "--",
        "estimated_supported_weight": f"{_value(weight)} g" if weight else "--",
    }
