"""Persist verified Battery 5A DATA frames into independent sessions."""

from __future__ import annotations

from database.repository.measurement_session_repository import MeasurementRepository
from database.repository.session_repository import SessionRepository
from measurement.battery_measurement_parser import parse_battery_data_frame
from measurement.battery_session import create_battery_session


class BatteryMeasurementIngestService:
    """Bridge Battery DATA frames to the common Session/Measurement repositories."""

    def __init__(self, database):
        self.database = database
        self.sessions = SessionRepository(database)
        self.measurements = MeasurementRepository(database)

    def start_channel(self, channel: str):
        session = create_battery_session(channel)
        self.sessions.insert(session)
        return session

    def ingest_frame(self, raw_frame: str | bytes, session_id: str):
        session = self.sessions.find(session_id)
        if session is None:
            raise ValueError(f"unknown Battery session: {session_id}")

        measurement = parse_battery_data_frame(raw_frame)
        if measurement.instance_id != session_id_channel(session):
            raise ValueError("Battery frame channel does not match session channel")

        measurement.session_id = session_id
        self.measurements.insert(measurement)
        session.add_measurement()
        self.sessions.update(session)
        return measurement

    def finish_channel(self, session):
        session.finish()
        self.sessions.update(session)
        return session


def session_id_channel(session) -> str:
    prefix = "Battery 5A independent channel "
    if not session.notes.startswith(prefix):
        raise ValueError("not a Battery 5A independent session")
    channel = session.notes[len(prefix):]
    if channel not in {"CH1", "CH2"}:
        raise ValueError("invalid Battery session channel")
    return channel
