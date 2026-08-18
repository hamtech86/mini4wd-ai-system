"""Session-to-result adapter for Battery benchmark analysis.

Kept as a thin adapter so the existing Measurement repository/model remains
unchanged. No raw Measurement field is updated by this module.
"""
from analysis.battery_benchmark import analyze_5a_measurements


def analyze_session_rows(rows):
    return analyze_5a_measurements(rows)
