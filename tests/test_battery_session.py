from measurement.battery_session import create_battery_session, create_startall_sessions
from measurement.measurement_session import MeasurementType, SessionStatus


def test_battery_session_uses_common_session_type():
    session = create_battery_session("CH1")
    assert session.measurement_type is MeasurementType.BATTERY_EVALUATION
    assert session.status is SessionStatus.RUNNING
    assert session.firmware_version == "BATTERY_DISCHARGER_V1"


def test_startall_creates_two_independent_sessions():
    sessions = create_startall_sessions()
    assert set(sessions) == {"CH1", "CH2"}
    assert sessions["CH1"].session_id != sessions["CH2"].session_id
    assert all(s.measurement_type is MeasurementType.BATTERY_EVALUATION for s in sessions.values())
