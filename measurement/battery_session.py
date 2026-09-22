"""Battery 5A session helpers.

STARTALL is represented by two independent sessions, one per channel.
"""

from __future__ import annotations

from measurement.measurement_session import MeasurementSession, MeasurementType


def create_battery_session(channel: str, firmware_version: str = "BATTERY_DISCHARGER_V1") -> MeasurementSession:
    if channel not in {"CH1", "CH2"}:
        raise ValueError("Battery session channel must be CH1 or CH2")

    session = MeasurementSession(
        measurement_type=MeasurementType.BATTERY_EVALUATION,
        firmware_version=firmware_version,
        notes=f"Battery 5A independent channel {channel}",
    )
    session.start()
    return session


def create_startall_sessions(firmware_version: str = "BATTERY_DISCHARGER_V1"):
    """Create independent CH1 and CH2 sessions for a STARTALL operation."""
    return {
        "CH1": create_battery_session("CH1", firmware_version),
        "CH2": create_battery_session("CH2", firmware_version),
    }
