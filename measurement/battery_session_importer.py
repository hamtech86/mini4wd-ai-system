"""Import verified Battery 5A DATA frames into independent Sessions.

STARTALL is represented by two independent channel sessions because the
firmware emits separate CH1 and CH2 DATA frames.
"""

from __future__ import annotations

from uuid import uuid4

from database.repository.measurement_session_repository import MeasurementRepository
from database.repository.session_repository import SessionRepository
from measurement.battery_measurement_parser import parse_battery_data_frame
from measurement.measurement_session import MeasurementSession, MeasurementType


class BatterySessionImporter:
    def __init__(self, database):
        self.database = database
        self.sessions = SessionRepository(database)
        self.measurements = MeasurementRepository(database)

    def start_session(self, instance_id: str, firmware_version: str = "BATTERY_DISCHARGER_V1") -> MeasurementSession:
        session = MeasurementSession(
            session_id=str(uuid4()),
            measurement_type=MeasurementType.BATTERY_5A,
            operator="SYSTEM",
            notes=f"Battery 5A channel {instance_id}",
            schema_version="1.0",
            firmware_version=firmware_version,
        )
        session.start()
        self.sessions.insert(session)
        return session

    @staticmethod
    def _channel_from_notes(session: MeasurementSession) -> str:
        return session.notes.rsplit(" ", 1)[-1]

    def import_frame(self, session: MeasurementSession, raw: str | bytes):
        measurement = parse_battery_data_frame(raw)
        if measurement.instance_id != self._channel_from_notes(session):
            raise ValueError("Battery DATA channel does not match Session channel")
        measurement.session_id = session.session_id
        self.measurements.insert(measurement)
        session.add_measurement()
        self.sessions.update(session)
        return measurement

    def finish_session(self, session: MeasurementSession):
        session.finish()
        self.sessions.update(session)
        return session

    def import_frames(self, session: MeasurementSession, frames):
        """Import a channel's DATA frames atomically; rollback on failure."""
        self.database.begin()
        try:
            for frame in frames:
                self.import_frame(session, frame)
            self.finish_session(session)
            self.database.commit()
        except Exception:
            self.database.rollback()
            raise
        return session
