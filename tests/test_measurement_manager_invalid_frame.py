from measurement.measurement_manager import MeasurementManager


class Serial:
    last_pwm = 80
    direction = "FWD"

    def __init__(self, frame):
        self.frame = frame

    def read_measurement(self):
        return self.frame


def test_missing_frame_is_not_a_measurement():
    manager = MeasurementManager(Serial(None))

    assert manager.collect() is None
    assert manager.last_measurement is None


def test_unknown_instance_frame_is_not_a_measurement():
    frame = (
        "DATA,MOTOR_BREAKIN_V3,UNKNOWN,0,514,515,"
        "0.000,0.000,0.056,0.056,0.000,80,FWD,RUNNING,"
        "0.000,0.000,0.000,0.000,0.000,0.000,0.000,0,"
        "0.000,541,2.644,21.5"
    )
    manager = MeasurementManager(Serial(frame))

    assert manager.collect() is None
    assert manager.last_measurement is None


def test_valid_frame_creates_measurement():
    frame = (
        "DATA,MOTOR_BREAKIN_V3,000001,139,504,509,"
        "0.283,0.156,2.842,1.254,1.588,80,FWD,RUN,"
        "0.219,0.348,0.259,1.588,0.000,0.000,0.000,0,"
        "0.000,541,2.644,21.5"
    )
    manager = MeasurementManager(Serial(frame))

    measurement = manager.collect()

    assert measurement is not None
    assert measurement.instance_id == "000001"
    assert measurement.elapsed_time == 139
    assert measurement.motor_voltage == 1.588
