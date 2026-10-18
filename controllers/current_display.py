"""Formatting helpers for the Main UI's physical measurement displays."""

import math


_VALID_DIRECTIONS = {"FWD", "REV"}


def format_motor_voltage(measurement):
    """Format the signed V4-V5 motor-terminal voltage without direction correction."""
    if measurement is None:
        return "--"
    try:
        value = getattr(measurement, "motor_voltage")
        if value is None:
            return "--"
        voltage = float(value)
    except (AttributeError, TypeError, ValueError, OverflowError):
        return "--"
    if not math.isfinite(voltage):
        return "--"
    return f"{voltage:.2f} V"


def format_driver_input_current(measurement):
    """Format ACS712 #1/A0 as driver input-path current.

    The project wiring definition places ACS712 #1 in the power-input path
    before the L298N. This is driver input current, not motor winding current.
    """
    if measurement is None:
        return "--"
    try:
        value = getattr(measurement, "current1")
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
