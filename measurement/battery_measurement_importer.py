"""Import verified Battery 5A DATA frames into Measurement storage."""
from __future__ import annotations

from database.repository.measurement_session_repository import MeasurementRepository
from measurement.battery_measurement_parser import parse_battery_data_frame


class BatteryMeasurementImporter:
    """Persist one verified Battery DATA frame without modifying its values."""

    def __init__(self, database):
        self.repository = MeasurementRepository(database)

    def import_frame(self, raw_frame: str | bytes, session_id: str):
        measurement = parse_battery_data_frame(raw_frame)
        measurement.session_id = session_id
        self.repository.insert(measurement)
        return measurement
