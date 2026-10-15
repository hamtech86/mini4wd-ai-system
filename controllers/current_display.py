"""Shared formatting for the ACS712 #1 high-side current display."""


def format_high_side_current(measurement):
    """Format sensor 1 current for Main UI; never substitute current_avg."""
    if measurement is None:
        return "--"
    return f"{float(getattr(measurement, 'current1', 0)):.3f} A"
