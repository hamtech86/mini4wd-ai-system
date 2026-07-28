"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 database_controller.py
=====================================================

Database Controller

MeasurementをDatabase層へ渡す。
ControllerはSQLを持たない。
"""

from __future__ import annotations

from typing import Optional

from measurement.measurement import Measurement


class DatabaseController:
    """
    Database Controller

    DatabaseManagerへの橋渡しのみを担当する。
    """

    def __init__(self):

        self.database = None

    def set_database_manager(self, manager):
        """
        DatabaseManagerを登録
        """

        self.database = manager

    @property
    def is_ready(self) -> bool:
        """
        Database接続状態
        """

        return self.database is not None

    def save_measurement(
        self,
        measurement: Measurement,
    ) -> bool:
        """
        Measurement保存
        """

        if self.database is None:
            return False

        self.database.save_measurement(
            measurement
        )

        return True

    def save_session(
        self,
        session,
    ) -> bool:
        """
        Session保存
        """

        if self.database is None:
            return False

        self.database.save_session(
            session
        )

        return True

