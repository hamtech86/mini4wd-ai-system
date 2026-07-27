"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 measurement.py
=====================================================

Measurement Data Model

Arduinoから取得したMeasurementの原本。
Measurementは事実のみを保持し、
Analysis結果は保持しない。
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class Measurement:
    """
    1サンプル分のMeasurement
    """

    # -------------------------------------------------
    # Header
    # -------------------------------------------------

    record_type: str
    device_model: str
    instance_id: str
    elapsed_time: int

    # -------------------------------------------------
    # ADC
    # -------------------------------------------------

    raw_acs1: int
    raw_acs2: int

    # -------------------------------------------------
    # Current
    # -------------------------------------------------

    current1: float
    current2: float

    # -------------------------------------------------
    # Voltage
    # -------------------------------------------------

    voltage1: float
    voltage2: float
    motor_voltage: float

    # -------------------------------------------------
    # Control
    # -------------------------------------------------

    pwm: int
    direction: str
    state: str

    # -------------------------------------------------
    # Statistics
    # -------------------------------------------------

    current_avg: float
    power: float
    current_ripple: float
    voltage_ripple: float

    # -------------------------------------------------
    # Peak
    # -------------------------------------------------

    peak_power: float
    peak_current: float
    peak_voltage: float
    peak_pwm: int

    brush_peak_current: float

    # -------------------------------------------------
    # Magnetic
    # -------------------------------------------------

    raw_magnetic: int
    magnetic_level: float

    # -------------------------------------------------
    # Temperature
    # -------------------------------------------------

    motor_temperature: float

    # -------------------------------------------------
    # Session
    # -------------------------------------------------

    session_id: Optional[str] = None

    # -------------------------------------------------
    # Version
    # -------------------------------------------------

    schema_version: str = "1.0"
    firmware_version: str = "MOTOR_BREAKIN_V3"

    # -------------------------------------------------
    # Utility
    # -------------------------------------------------

    @property
    def electrical_power(self) -> float:
        """
        電圧×電流から求めた瞬時電力
        """

        return self.motor_voltage * self.current1

    @property
    def is_running(self) -> bool:
        """
        モーター回転中判定
        """

        return self.pwm > 0

