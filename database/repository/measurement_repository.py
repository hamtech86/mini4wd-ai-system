"""
MINI4WD AI SYSTEM
MOTOR_BREAKIN_V3
Measurement Repository
"""

from __future__ import annotations

from database.manager.database_manager import DatabaseManager
from measurement.measurement import Measurement


class MeasurementRepository:
    """measurementテーブルへのアクセスを担当する。"""

    TABLE_NAME = "measurement"

    def __init__(self, database: DatabaseManager):
        self.database = database

    def insert(self, measurement: Measurement) -> None:
        if not measurement.session_id:
            raise ValueError("measurement.session_id is required")

        sql = f"""
        INSERT INTO {self.TABLE_NAME} (
            session_id, record_type, device_model, instance_id, elapsed_time,
            raw_acs1, raw_acs2, current1, current2, voltage1, voltage2,
            motor_voltage, pwm, direction, state, current_avg, power,
            current_ripple, voltage_ripple, peak_power, peak_current,
            peak_voltage, peak_pwm, brush_peak_current, raw_magnetic,
            magnetic_level, motor_temperature
        ) VALUES (
            ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?
        )
        """

        self.database.execute(sql, (
            measurement.session_id,
            measurement.record_type,
            measurement.device_model,
            measurement.instance_id,
            measurement.elapsed_time,
            measurement.raw_acs1,
            measurement.raw_acs2,
            measurement.current1,
            measurement.current2,
            measurement.voltage1,
            measurement.voltage2,
            measurement.motor_voltage,
            measurement.pwm,
            measurement.direction,
            measurement.state,
            measurement.current_avg,
            measurement.power,
            measurement.current_ripple,
            measurement.voltage_ripple,
            measurement.peak_power,
            measurement.peak_current,
            measurement.peak_voltage,
            measurement.peak_pwm,
            measurement.brush_peak_current,
            measurement.raw_magnetic,
            measurement.magnetic_level,
            measurement.motor_temperature,
        ))

    def count_by_session(self, session_id: str) -> int:
        cursor = self.database.execute(
            f"SELECT COUNT(*) FROM {self.TABLE_NAME} WHERE session_id=?",
            (session_id,),
        )
        return int(cursor.fetchone()[0])
