"""Legacy session-level feature extractor with explicit channel isolation."""
from __future__ import annotations
from math import isfinite
from statistics import mean, pstdev


def extract_battery_benchmark(measurements, *, channel):
    """Return one channel's features; never fall back to the other channel."""
    if channel not in ("CH1", "CH2"):
        raise ValueError("channel must be explicitly set to 'CH1' or 'CH2'")
    rows = list(measurements)
    if not rows:
        raise ValueError("no Battery measurements")
    voltage_key = "voltage1" if channel == "CH1" else "voltage2"
    current_key = "current1" if channel == "CH1" else "current2"

    def numeric(row, key):
        value = getattr(row, key, None)
        if value is None:
            return None
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        return value if isfinite(value) else None

    samples = []
    for row in rows:
        voltage = numeric(row, voltage_key)
        current = numeric(row, current_key)
        elapsed = numeric(row, "elapsed_time")
        if voltage is None or current is None or elapsed is None:
            continue
        samples.append((elapsed, voltage, current))
    if not samples:
        raise ValueError(f"no valid {channel} voltage/current samples")
    samples.sort(key=lambda item: item[0])
    voltages = [sample[1] for sample in samples]
    currents = [sample[2] for sample in samples]
    powers = [v * i for v, i in zip(voltages, currents)]
    capacity_ah = 0.0
    energy_wh = 0.0
    for a, b in zip(samples, samples[1:]):
        dt_h = (b[0] - a[0]) / 3600000.0
        capacity_ah += ((a[2] + b[2]) / 2) * dt_h
        energy_wh += ((a[1] * a[2] + b[1] * b[2]) / 2) * dt_h
    return {
        "measurement_count": len(samples), "channel": channel,
        "avg_voltage": mean(voltages), "avg_current": mean(currents), "avg_power": mean(powers),
        "max_current": max(currents), "max_power": max(powers),
        "discharge_time_s": (samples[-1][0] - samples[0][0]) / 1000.0,
        "voltage_drop": voltages[0] - voltages[-1],
        "capacity_ah": capacity_ah, "capacity_mah": capacity_ah * 1000.0,
        "energy_wh": energy_wh,
        "voltage_stddev": pstdev(voltages) if len(voltages) > 1 else 0.0,
        "current_stddev": pstdev(currents) if len(currents) > 1 else 0.0,
        "power_stddev": pstdev(powers) if len(powers) > 1 else 0.0,
        "internal_resistance_mohm": None, "capacity_score": None,
        "voltage_hold_score": None, "stability_score": None,
        "power_score": None, "overall_score": None,
    }
