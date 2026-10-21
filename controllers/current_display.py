"""Formatting helpers for physical sensor values shown in the operator UI."""
import math


def _finite_value(measurement, field):
    if measurement is None:
        return None
    try:
        value = getattr(measurement, field)
        if value is None:
            return None
        value = float(value)
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None
    return value if math.isfinite(value) else None


def format_motor_voltage(measurement):
    value = _finite_value(measurement, "motor_voltage")
    return "--" if value is None else f"{value:.2f} V"


def format_driver_input_current(measurement):
    # ACS712 #1/A0 is defined as the driver input-path sensor, not winding current.
    value = _finite_value(measurement, "current1")
    return "--" if value is None else f"{value:.3f} A"


def format_input_voltage(measurement, direction=None):
    selected_direction = str(direction or getattr(measurement, "direction", "")).upper()
    if selected_direction not in {"FWD", "REV"}:
        return "--"
    field = "voltage1" if selected_direction == "FWD" else "voltage2"
    value = _finite_value(measurement, field)
    return "--" if value is None else f"{value:.2f} V"
