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


class BatterySampleValidityUnknown(ValueError):
    """Selected-channel zero value has no authoritative validity semantics."""


def _channel_values(rows: list[Mapping], channel: str, metric: str) -> list[float]:
    if channel not in ("CH1", "CH2"):
        raise ValueError("channel must be explicitly set to 'CH1' or 'CH2'")
    if metric not in ("voltage", "current"):
        raise ValueError("unsupported Battery metric")
    key = f"{metric}{1 if channel == 'CH1' else 2}"
    values = []
    for index, row in enumerate(rows):
        value = _finite_value(row, key)
        if value == 0.0:
            raise BatterySampleValidityUnknown(
                f"{channel} {metric} is 0.0 at row {index}; validity is UNKNOWN"
            )
        if value is not None:
            values.append(value)
    return values


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
    voltage_key = "voltage1" if channel == "CH1" else "voltage2"
    current_key = "current1" if channel == "CH1" else "current2"
    samples = []
    for row in rows:
        voltage = _finite_value(row, voltage_key)
        current = _finite_value(row, current_key)
        elapsed = next(
            (_finite_value(row, key) for key in ("elapsed_time", "elapsed_s", "time_s") if row.get(key) is not None),
            None,
        )
        # The firmware and Battery spec do not define selected-channel 0.0
        # as an inactive sentinel. Preserve the raw row and fail closed rather
        # than silently dropping it from derived values.
        if voltage == 0.0 or current == 0.0:
            metric = "voltage" if voltage == 0.0 else "current"
            raise BatterySampleValidityUnknown(
                f"{channel} {metric} is 0.0; validity is UNKNOWN and derived result is ineligible"
            )
        if voltage is None or current is None or elapsed is None:
            raise BatterySampleValidityUnknown(
                f"{channel} sample row is incomplete or non-finite; validity is UNKNOWN"
            )
        samples.append((elapsed, voltage, current))
    if not samples:
        raise BatterySampleValidityUnknown(f"{channel} has no complete valid samples; validity is UNKNOWN")
    voltages = [sample[1] for sample in samples]
    currents = [sample[2] for sample in samples]
    powers = [voltage * current for voltage, current in zip(voltages, currents)]
    times = [sample[0] for sample in samples if sample[0] is not None]

    avg_voltage = mean(voltages) if voltages else None
    avg_current = mean(currents) if currents else None
    avg_power = mean(powers) if powers else None
    max_current = max(currents) if currents else None
    max_power = max(powers) if powers else None
    discharge_time_s = max(times) - min(times) if len(times) >= 2 else None
    voltage_drop = voltages[0] - voltages[-1] if len(voltages) >= 2 else None

    has_complete_timestamps = len(times) == len(samples)
    capacity_ah = _trapz(times, currents) / 3600.0 if has_complete_timestamps and len(times) >= 2 else None
    energy_wh = _trapz(times, powers) / 3600.0 if has_complete_timestamps and len(times) >= 2 else None

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
