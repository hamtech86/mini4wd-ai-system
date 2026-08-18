"""Benchmark analysis for Battery 5A measurements.

The analyzer consumes raw Measurement-like dictionaries and returns derived
features. It never mutates the source measurements and deliberately does not
invent an internal-resistance calculation.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from math import sqrt
from statistics import mean
from typing import Iterable, Mapping, Optional


ANALYSIS_VERSION = "battery-benchmark-v1"


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


def _values(rows: list[Mapping], *keys: str) -> list[float]:
    result = []
    for row in rows:
        value = next((row.get(k) for k in keys if row.get(k) is not None), None)
        if value is not None:
            try:
                result.append(float(value))
            except (TypeError, ValueError):
                pass
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
    analysis_version: str = ANALYSIS_VERSION,
) -> dict:
    """Extract benchmark features from 5A discharge measurements.

    Accepted aliases reflect the existing common Measurement schema:
    voltage1/voltage2, current1/current2, power and elapsed_time.
    For a two-channel record, voltage/current values are averaged per row.

    No scoring baseline is assumed. Score fields therefore remain ``None``
    until a validated benchmark reference is supplied.
    """
    rows = list(measurements)
    voltages = _values(rows, "voltage1", "voltage", "battery_voltage", "voltage2")
    currents = _values(rows, "current1", "current", "discharge_current", "current2")
    powers = _values(rows, "power", "discharge_power")
    times = _values(rows, "elapsed_time", "elapsed_s", "time_s")

    # Prefer a per-row channel average when both channels are present.
    voltages = [
        (float(r["voltage1"]) + float(r["voltage2"])) / 2.0
        if r.get("voltage1") is not None and r.get("voltage2") is not None
        else v
        for r, v in zip(rows, voltages)
    ]
    currents = [
        (float(r["current1"]) + float(r["current2"])) / 2.0
        if r.get("current1") is not None and r.get("current2") is not None
        else i
        for r, i in zip(rows, currents)
    ]

    if not powers and voltages and currents and len(voltages) == len(currents):
        powers = [v * i for v, i in zip(voltages, currents)]

    avg_voltage = mean(voltages) if voltages else None
    avg_current = mean(currents) if currents else None
    avg_power = mean(powers) if powers else None
    max_current = max(currents) if currents else None
    max_power = max(powers) if powers else None

    discharge_time_s = (max(times) - min(times)) if len(times) >= 2 else None
    voltage_drop = (voltages[0] - voltages[-1]) if len(voltages) >= 2 else None

    capacity_ah = None
    energy_wh = None
    if len(times) == len(currents) and len(times) >= 2:
        capacity_ah = _trapz(times, currents) / 3600.0
    if len(times) == len(powers) and len(times) >= 2:
        energy_wh = _trapz(times, powers) / 3600.0

    return BatteryBenchmarkResult(
        measurement_count=len(rows),
        avg_voltage=avg_voltage,
        avg_current=avg_current,
        avg_power=avg_power,
        max_current=max_current,
        max_power=max_power,
        discharge_time_s=discharge_time_s,
        voltage_drop=voltage_drop,
        capacity_ah=capacity_ah,
        capacity_mah=capacity_ah * 1000.0 if capacity_ah is not None else None,
        energy_wh=energy_wh,
        voltage_stddev=_stddev(voltages),
        current_stddev=_stddev(currents),
        power_stddev=_stddev(powers),
        # Scores intentionally not inferred without a validated reference.
        voltage_hold_score=None,
        stability_score=None,
        capacity_score=None,
        power_score=None,
        overall_score=None,
        # Internal resistance is intentionally not estimated from 5A samples.
        internal_resistance_mohm=None,
    ).to_dict() | {"analysis_version": analysis_version}
