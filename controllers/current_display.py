"""Shared formatting for the ACS712 #1 high-side current display."""

import math


def format_high_side_current(measurement):
    """Format sensor 1 current; unavailable or invalid values display as '--'."""
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
