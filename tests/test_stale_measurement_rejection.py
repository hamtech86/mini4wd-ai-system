"""A rejected/missing DATA frame must not leave stale UI measurements."""
from measurement.measurement_manager import MeasurementManager


class InvalidFrameSerial:
    def read_measurement(self):
        return {"record_type": "DATA", "voltage1": float("nan")}


def test_invalid_frame_clears_last_measurement():
    manager = MeasurementManager(serial_controller=InvalidFrameSerial())
    manager.last_measurement = object()

    assert manager.collect() is None
    assert manager.last_measurement is None
