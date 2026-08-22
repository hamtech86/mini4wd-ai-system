"""Second-stage Battery Analysis.

Consumes an existing Battery Benchmark Result and produces presentation-ready
analysis data. The benchmark result and raw measurements are never mutated.

This module intentionally does not invent evaluation thresholds or internal
resistance calculations. Missing inputs are represented explicitly and added
to warnings so the UI can display an honest result.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping, Optional

ANALYSIS_VERSION = "battery-analysis-v1"


@dataclass(frozen=True)
class BatteryAnalysisResult:
    analysis_version: str
    benchmark_id: Optional[int]
    session_id: Optional[str]
    instance_id: Optional[str]
    average_voltage: Optional[float]
    average_current: Optional[float]
    average_power: Optional[float]
    max_current: Optional[float]
    max_power: Optional[float]
    discharge_time_s: Optional[float]
    capacity_mah: Optional[float]
    energy_wh: Optional[float]
    voltage_drop: Optional[float]
    voltage_drop_rate: Optional[float]
    voltage_stddev: Optional[float]
    current_stddev: Optional[float]
    power_stddev: Optional[float]
    stability: str
    rank: Optional[str]
    internal_resistance_mohm: Optional[float]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict:
        value = asdict(self)
        value["warnings"] = list(self.warnings)
        return value


def _number(result: Mapping, key: str) -> Optional[float]:
    value = result.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def analyze_benchmark_result(
    benchmark_result: Mapping,
    *,
    analysis_version: str = ANALYSIS_VERSION,
) -> BatteryAnalysisResult:
    """Generate a deterministic Battery Analysis Result from one benchmark.

    The current benchmark schema contains voltage_drop but not start/end
    voltage. Therefore voltage_drop_rate is deliberately left unavailable
    rather than estimating it from average voltage.
    """
    warnings: list[str] = []

    count = benchmark_result.get("measurement_count")
    try:
        count = int(count) if count is not None else 0
    except (TypeError, ValueError):
        count = 0
    if count <= 0:
        warnings.append("no_measurements")

    internal_resistance = _number(benchmark_result, "internal_resistance_mohm")
    if internal_resistance is None:
        warnings.append("internal_resistance_not_evaluated")

    # No start/end voltage fields exist in the current Benchmark Result.
    warnings.append("voltage_drop_rate_unavailable_without_start_end_voltage")

    # No approved thresholds exist yet, so do not manufacture a rank.
    warnings.append("evaluation_thresholds_not_configured")

    voltage_stddev = _number(benchmark_result, "voltage_stddev")
    current_stddev = _number(benchmark_result, "current_stddev")
    power_stddev = _number(benchmark_result, "power_stddev")
    if voltage_stddev is None and current_stddev is None and power_stddev is None:
        stability = "UNAVAILABLE"
        warnings.append("stability_metrics_unavailable")
    else:
        # The measured variation is exposed, but no pass/fail threshold is
        # assigned until an approved benchmark/config is supplied.
        stability = "UNSCORED"

    return BatteryAnalysisResult(
        analysis_version=analysis_version,
        benchmark_id=benchmark_result.get("result_id"),
        session_id=benchmark_result.get("session_id"),
        instance_id=benchmark_result.get("instance_id"),
        average_voltage=_number(benchmark_result, "avg_voltage"),
        average_current=_number(benchmark_result, "avg_current"),
        average_power=_number(benchmark_result, "avg_power"),
        max_current=_number(benchmark_result, "max_current"),
        max_power=_number(benchmark_result, "max_power"),
        discharge_time_s=_number(benchmark_result, "discharge_time_s"),
        capacity_mah=_number(benchmark_result, "capacity_mah"),
        energy_wh=_number(benchmark_result, "energy_wh"),
        voltage_drop=_number(benchmark_result, "voltage_drop"),
        voltage_drop_rate=None,
        voltage_stddev=voltage_stddev,
        current_stddev=current_stddev,
        power_stddev=power_stddev,
        stability=stability,
        rank=None,
        internal_resistance_mohm=internal_resistance,
        warnings=tuple(warnings),
    )
