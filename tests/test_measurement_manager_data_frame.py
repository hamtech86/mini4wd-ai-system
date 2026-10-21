from measurement.measurement_manager import MeasurementManager


class FakeSerialController:
    def __init__(self, frame):
        self.frame = frame

    def read_measurement(self):
        return self.frame


def data_frame(motor_voltage="-3.08"):
    return ",".join([
        "DATA", "MOTOR_BREAKIN_V3", "INSTANCE-7", "1234",
        "512", "511", "0.123", "0.110", "3.10", "0.02",
        motor_voltage, "80", "REV", "RUNNING", "0.116", "0.36",
        "0.01", "0.02", "0.40", "0.20", "3.10", "80",
        "0.20", "0", "0.0", "25.0",
    ])


def test_collect_parses_serial_data_csv_and_preserves_signed_motor_voltage():
    manager = MeasurementManager(FakeSerialController(data_frame()))

    measurement = manager.collect()

    assert measurement is not None
    assert measurement.record_type == "DATA"
    assert measurement.instance_id == "INSTANCE-7"
    assert measurement.direction == "REV"
    assert measurement.current1 == 0.123
    assert measurement.voltage1 == 3.10
    assert measurement.voltage2 == 0.02
    assert measurement.motor_voltage == -3.08
    assert manager.last_measurement is measurement


def test_collect_rejects_malformed_csv_without_fabricating_measurement():
    manager = MeasurementManager(FakeSerialController("DATA,too,few,columns"))

    assert manager.collect() is None
    assert manager.last_measurement is None


def test_signed_motor_voltage_outside_physical_range_is_rejected():
    manager = MeasurementManager(FakeSerialController(data_frame(motor_voltage="-12.1")))

    assert manager.collect() is None
    assert manager.last_measurement is None
