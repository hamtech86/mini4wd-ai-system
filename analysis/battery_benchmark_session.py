"""Session-level Battery benchmark feature extraction."""
from __future__ import annotations
from statistics import mean, pstdev


def extract_battery_benchmark(measurements):
    """Return derived benchmark features without modifying measurements."""
    rows = list(measurements)
    if not rows:
        raise ValueError("no Battery measurements")
    channels = {getattr(row, "instance_id", None) for row in rows}
    if len(channels) != 1:
        raise ValueError("Battery benchmark requires one independent channel")
    voltages = [float(row.voltage1 or row.voltage2) for row in rows]
    currents = [float(row.current1 or row.current2) for row in rows]
    powers = [float(row.power) for row in rows]
    times_ms = [float(row.elapsed_time) for row in rows]
    capacity_ah = 0.0
    energy_wh = 0.0
    for a, b in zip(rows, rows[1:]):
        dt_h = (float(b.elapsed_time) - float(a.elapsed_time)) / 3600000.0
        i1, i2 = float(a.current1 or a.current2), float(b.current1 or b.current2)
        v1, v2 = float(a.voltage1 or a.voltage2), float(b.voltage1 or b.voltage2)
        capacity_ah += ((i1 + i2) / 2) * dt_h
        energy_wh += (((i1 * v1) + (i2 * v2)) / 2) * dt_h
    return {
        "measurement_count": len(rows), "channel": next(iter(channels)),
        "avg_voltage": mean(voltages), "avg_current": mean(currents), "avg_power": mean(powers),
        "max_current": max(currents), "max_power": max(powers),
        "discharge_time_s": max(times_ms) / 1000.0,
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
