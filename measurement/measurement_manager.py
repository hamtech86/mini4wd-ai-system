"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 measurement_manager.py
=====================================================

Measurement Manager

Measurement層の中核クラス。

責務

・dict → Measurement生成
・Measurement Session管理
・Measurement Logger管理
・Measurement Filter管理

Analysis・Database・UIは
このクラスからMeasurementを受け取る。
"""

from __future__ import annotations

from typing import Dict, Optional

from measurement.measurement import Measurement
from measurement.measurement_logger import MeasurementLogger
from measurement.measurement_session import (
    MeasurementSession,
    MeasurementType,
)
from measurement.filters import FilterGroup


class MeasurementManager:
    """
    Measurement Manager
    """

    def __init__(self):

        self.session: Optional[MeasurementSession] = None

        self.logger = MeasurementLogger()

        self.filters = FilterGroup()

        self.last_measurement: Optional[Measurement] = None

    @property
    def is_running(self) -> bool:

        return (
            self.session is not None
            and self.session.is_running
        )

    def start_session(
        self,
        measurement_type: MeasurementType = MeasurementType.BREAKIN,
    ):

        self.session = MeasurementSession(
            measurement_type=measurement_type
        )

        self.session.start()

        self.logger.start(self.session.session_id)

        self.filters.reset()

    def finish_session(self):

        if self.session is None:
            return

        self.session.finish()

        self.logger.stop()

    def cancel_session(self):

        if self.session is None:
            return

        self.session.cancel()

        self.logger.stop()

    def create_measurement(
        self,
        data: Dict,
    ) -> Measurement:
        """
        dict → Measurement
        """

        measurement = Measurement(**data)

        if self.session is not None:

            measurement.session_id = self.session.session_id

            self.session.add_measurement()

        #
        # Measurement用フィルタ
        #

        self.filters.current.update(
            measurement.current1
        )

        self.filters.voltage.update(
            measurement.motor_voltage
        )

        self.filters.power.update(
            measurement.electrical_power
        )

        #
        # Logger
        #

        self.logger.write(measurement)

        #
        # Cache
        #

        self.last_measurement = measurement

        return measurement

    @property
    def filtered_current(self) -> float:

        return self.filters.current.value

    @property
    def filtered_voltage(self) -> float:

        return self.filters.voltage.value

    @property
    def filtered_power(self) -> float:

        return self.filters.power.value

