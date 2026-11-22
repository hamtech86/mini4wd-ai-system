"""Benchmark analysis for one explicitly selected Battery channel.

Raw Measurement rows are immutable inputs. A call analyzes exactly one
channel; it never averages, sums, or falls back to the other channel.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from math import isfinite, sqrt
from statistics import mean
from typing import Iterable, Mapping, Optional

ANALYSIS_VERSION = "battery-benchmark-v2"


@dataclass(frozen=True)
class BatteryBenchmarkResult:
    measurement_count: int
    avg_voltage: Optional[float]
    avg_current: Optional[float]
    avg_power: Optional[float]
    max_current: Optional[float]
    max_power: Optional[float]
    discharge_time_s: Optional[float]
    voltage_drop: Optional[float]
    capacity_ah: Optional[float]
    capacity_mah: Optional[float]
    energy_wh: Optional[float]
    voltage_stddev: Optional[float]
    current_stddev: Optional[float]
    power_stddev: Optional[float]
    voltage_hold_score: Optional[float] = None
    stability_score: Optional[float] = None
    capacity_score: Optional[float] = None
    power_score: Optional[float] = None
    overall_score: Optional[float] = None
    internal_resistance_mohm: Optional[float] = None

    def to_dict(self):
        return asdict(self)


def _finite_value(row: Mapping, key: str) -> Optional[float]:
    value = row.get(key)
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _channel_values(rows: list[Mapping], channel: str, metric: str) -> list[float]:
    if channel not in ("CH1", "CH2"):
        raise ValueError("channel must be explicitly set to 'CH1' or 'CH2'")
    if metric not in ("voltage", "current"):
        raise ValueError("unsupported Battery metric")
    key = f"{metric}{1 if channel == 'CH1' else 2}"
    return [value for row in rows if (value := _finite_value(row, key)) is not None and value != 0.0]


def _values(rows: list[Mapping], *keys: str) -> list[float]:
    result = []
    for row in rows:
        value = next((_finite_value(row, key) for key in keys if row.get(key) is not None), None)
        if value is not None:
            result.append(value)
    return result


def _stddev(values: list[float]) -> Optional[float]:
    if not values:
        return None
    if len(values) == 1:
        return 0.0
    avg = mean(values)
    return sqrt(sum((x - avg) ** 2 for x in values) / len(values))


def _trapz(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 2:
        return 0.0
    pairs = sorted(zip(xs, ys), key=lambda p: p[0])
    return sum((t1 - t0) * (v0 + v1) / 2.0 for (t0, v0), (t1, v1) in zip(pairs, pairs[1:]))


def analyze_5a_measurements(
    measurements: Iterable[Mapping],
    *,
    channel: str,
    analysis_version: str = ANALYSIS_VERSION,
) -> dict:
    """Extract features for exactly one explicitly selected Battery channel."""
    if channel not in ("CH1", "CH2"):
        raise ValueError("channel must be explicitly set to 'CH1' or 'CH2'")
    rows = list(measurements)
    voltages = _channel_values(rows, channel, "voltage")
    currents = _channel_values(rows, channel, "current")
    times = _values(rows, "elapsed_time", "elapsed_s", "time_s")

    # A generic power column is ambiguous when both channels coexist in one
    # Measurement row. Derive power from the selected channel's own V and I.
    powers = [v * i for v, i in zip(voltages, currents)] if len(voltages) == len(currents) else []

    avg_voltage = mean(voltages) if voltages else None
    avg_current = mean(currents) if currents else None
    avg_power = mean(powers) if powers else None
    max_current = max(currents) if currents else None
    max_power = max(powers) if powers else None
    discharge_time_s = max(times) - min(times) if len(times) >= 2 else None
    voltage_drop = voltages[0] - voltages[-1] if len(voltages) >= 2 else None

    capacity_ah = _trapz(times, currents) / 3600.0 if len(times) == len(currents) and len(times) >= 2 else None
    energy_wh = _trapz(times, powers) / 3600.0 if len(times) == len(powers) and len(times) >= 2 else None

    return BatteryBenchmarkResult(
        measurement_count=len(rows), avg_voltage=avg_voltage, avg_current=avg_current,
        avg_power=avg_power, max_current=max_current, max_power=max_power,
        discharge_time_s=discharge_time_s, voltage_drop=voltage_drop,
        capacity_ah=capacity_ah,
        capacity_mah=capacity_ah * 1000.0 if capacity_ah is not None else None,
        energy_wh=energy_wh, voltage_stddev=_stddev(voltages),
        current_stddev=_stddev(currents), power_stddev=_stddev(powers),
        voltage_hold_score=None, stability_score=None, capacity_score=None,
        power_score=None, overall_score=None, internal_resistance_mohm=None,
    ).to_dict() | {"analysis_version": analysis_version, "channel": channel}
