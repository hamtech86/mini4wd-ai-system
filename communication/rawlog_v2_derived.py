"""Derived-record adapters and conservative multi-sample summaries.

This module never changes AUX/raw records or selects calibration/policy values.
All thresholds and minimum sample counts are explicit caller inputs.
"""
from __future__ import annotations

import math
import statistics
from dataclasses import asdict
from typing import Iterable

from .rawlog_v2_analysis import ChannelValue, WindingResistanceResult


def winding_result_to_derived(result: WindingResistanceResult) -> dict:
    """Adapt one point result to the RawLog v2 Derived storage contract."""
    return {
        "metric": "winding_resistance_point",
        "algorithm_id": result.algorithm_id,
        "algorithm_version": result.algorithm_version,
        "input_sample_ids": list(result.input_sample_ids),
        "value": result.resistance_ohm if result.valid else None,
        "unit": "ohm",
        "valid": result.valid,
        "invalid_reason": result.invalid_reason,
    }


def summarize_a1_brush_signal(samples: Iterable[ChannelValue]) -> list[dict]:
    """Return descriptive A1 signal statistics, not a brush-stability score.

    Values must already be calibrated by the caller. Only A1 samples are used.
    """
    values = list(samples)
    if not values:
        return []
    if any(item.channel != "A1" for item in values):
        raise ValueError("brush signal summary accepts A1 samples only")
    units = {item.unit for item in values}
    if len(units) != 1:
        raise ValueError("A1 samples must use one consistent unit")
    numbers = [float(item.value) for item in values]
    if any(not math.isfinite(value) for value in numbers):
        raise ValueError("A1 values must be finite")
    ids = [item.sample_id for item in values]
    unit = next(iter(units))
    algorithm_id = "a1_brush_signal_descriptive_stats"
    version = "0.1.0"
    metrics = [
        ("a1_mean", statistics.fmean(numbers)),
        ("a1_min", min(numbers)),
        ("a1_max", max(numbers)),
        ("a1_range", max(numbers) - min(numbers)),
    ]
    if len(numbers) >= 2:
        metrics.append(("a1_population_stddev", statistics.pstdev(numbers)))
    return [
        {
            "metric": metric,
            "algorithm_id": algorithm_id,
            "algorithm_version": version,
            "input_sample_ids": ids,
            "value": value,
            "unit": unit,
            "valid": True,
            "invalid_reason": None,
        }
        for metric, value in metrics
    ]


def aggregate_winding_resistance(
    results: Iterable[WindingResistanceResult],
    *,
    minimum_valid_samples: int,
    maximum_range_ohm: float | None = None,
) -> dict:
    """Aggregate valid point estimates; quality policy is always caller-owned."""
    if type(minimum_valid_samples) is not int or minimum_valid_samples < 1:
        raise ValueError("minimum_valid_samples must be an explicit positive integer")
    if maximum_range_ohm is not None and (
        isinstance(maximum_range_ohm, bool)
        or not isinstance(maximum_range_ohm, (int, float))
        or not math.isfinite(float(maximum_range_ohm))
        or maximum_range_ohm < 0
    ):
        raise ValueError("maximum_range_ohm must be finite and non-negative")
    rows = list(results)
    valid = [item for item in rows if item.valid and item.resistance_ohm is not None]
    ids = sorted({sample_id for item in valid for sample_id in item.input_sample_ids})
    algorithm_id = "winding_resistance_multi_sample_summary"
    version = "0.1.0"
    if len(valid) < minimum_valid_samples:
        return {
            "metric": "winding_resistance_median",
            "algorithm_id": algorithm_id,
            "algorithm_version": version,
            "input_sample_ids": ids or sorted({
                sample_id for item in rows for sample_id in item.input_sample_ids
            }),
            "value": None,
            "unit": "ohm",
            "valid": False,
            "invalid_reason": (
                f"insufficient valid samples: {len(valid)} < {minimum_valid_samples}"
            ),
        }
    numbers = [float(item.resistance_ohm) for item in valid]
    spread = max(numbers) - min(numbers)
    if maximum_range_ohm is not None and spread > maximum_range_ohm:
        return {
            "metric": "winding_resistance_median",
            "algorithm_id": algorithm_id,
            "algorithm_version": version,
            "input_sample_ids": ids,
            "value": None,
            "unit": "ohm",
            "valid": False,
            "invalid_reason": (
                f"resistance range {spread} ohm exceeds configured maximum "
                f"{maximum_range_ohm} ohm"
            ),
        }
    return {
        "metric": "winding_resistance_median",
        "algorithm_id": algorithm_id,
        "algorithm_version": version,
        "input_sample_ids": ids,
        "value": statistics.median(numbers),
        "unit": "ohm",
        "valid": True,
        "invalid_reason": None,
    }
