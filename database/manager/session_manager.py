"""
MINI4WD AI SYSTEM
MOTOR_BREAKIN_V3

Production session lifecycle adapter for BreakinController.
"""

from measurement.measurement_session import MeasurementSession
from database.repository.session_repository import SessionRepository


class SessionManager:
    """Create and persist MeasurementSession lifecycle state."""

    def __init__(self, database):
        self.database = database
        self.repository = SessionRepository(database)
        self.current_session = None

    def start(self, measurement_type="BREAKIN", instance_id=None):
        """Start a DB-backed session for an explicitly selected motor instance."""
        if instance_id is None:
            raise ValueError(
                "instance_id is required to start a production measurement session"
            )

        session = MeasurementSession(instance_id=int(instance_id))
        session.measurement_type = session.measurement_type.__class__[measurement_type]
        session.start()
        self.repository.insert(session)
        self.database.commit()
        self.current_session = session
        return session

    def finish(self, result="COMPLETE"):
        if self.current_session is None:
            return None

        if result == "COMPLETE":
            self.current_session.finish()
        elif result == "ERROR":
            self.current_session.error()
        elif result == "CANCELLED":
            self.current_session.cancel()
        else:
            raise ValueError(f"Unsupported session result: {result}")

        self.repository.update(self.current_session)
        self.current_session.measurement_count = self._measurement_count(
            self.current_session.session_id
        )
        self.repository.update(self.current_session)
        self.database.commit()
        return self.current_session

    def _measurement_count(self, session_id):
        cursor = self.database.execute(
            "SELECT COUNT(*) FROM measurement WHERE session_id=?",
            (session_id,),
        )
        return cursor.fetchone()[0]
