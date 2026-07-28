"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 session_controller.py
=====================================================

Measurement Session Controller
"""

from __future__ import annotations

from typing import Optional

from measurement.measurement_session import (
    MeasurementSession,
    MeasurementType,
)


class SessionController:
    """
    Measurement Session管理
    """

    def __init__(self):

        self._session: Optional[
            MeasurementSession
        ] = None

    @property
    def session(self) -> Optional[MeasurementSession]:

        return self._session

    @property
    def is_running(self) -> bool:

        return (
            self._session is not None
            and self._session.is_running
        )

    def start(
        self,
        measurement_type: MeasurementType,
    ) -> MeasurementSession:

        self._session = MeasurementSession(
            measurement_type=measurement_type
        )

        self._session.start()

        return self._session

    def finish(self):

        if self._session is not None:
            self._session.finish()

    def cancel(self):

        if self._session is not None:
            self._session.cancel()

    def error(self):

        if self._session is not None:
            self._session.error()

    def add_measurement(self):

        if self._session is not None:
            self._session.add_measurement()

