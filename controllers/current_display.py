"""Formatting helpers for the Main UI's physical measurement displays."""

import math


_VALID_DIRECTIONS = {"FWD", "REV"}


def format_high_side_current(measurement):
    """Format current only when the backend explicitly identifies it as high-side.

    DATA.current1 maps to ACS712 #1/A0, but the firmware does not establish
    that this sensor is physically the high-side sensor. Do not infer that
    wiring role in the UI.
    """
    if measurement is None:
        return "--"
    try:
        value = getattr(measurement, "high_side_current")
        if value is None:
            return "--"
        current = float(value)
    except (AttributeError, TypeError, ValueError, OverflowError):
        return "--"
    if not math.isfinite(current):
        return "--"
    return f"{current:.3f} A"


def format_input_voltage(measurement, direction=None):
    """Format the physical input-side voltage for the active motor direction.

    FWD uses voltage1 (A4/VM1); REV uses voltage2 (A5/VM2). This is not
    the signed motor-terminal differential voltage.
    """
    if measurement is None:
        return "--"
    selected_direction = direction or getattr(measurement, "direction", None)
    if selected_direction not in _VALID_DIRECTIONS:
        return "--"
    field = "voltage1" if selected_direction == "FWD" else "voltage2"
    try:
        value = getattr(measurement, field)
        if value is None:
            return "--"
        voltage = float(value)
    except (AttributeError, TypeError, ValueError, OverflowError):
        return "--"
    if not math.isfinite(voltage):
        return "--"
    return f"{voltage:.2f} V"
