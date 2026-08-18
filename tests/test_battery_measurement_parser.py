import pytest

from measurement.battery_measurement_parser import BatteryMeasurementParseError, parse_battery_data_frame


def test_parse_verified_ch1_frame():
    m = parse_battery_data_frame(
        "DATA,BATTERY_DISCHARGER_V1,CH1,12500,4.982,1.284,0,73,0,RUN"
    )
    assert m.device_model == "BATTERY_DISCHARGER_V1"
    assert m.instance_id == "CH1"
    assert m.elapsed_time == 12500
    assert m.current1 == pytest.approx(4.982)
    assert m.current2 == 0.0
    assert m.voltage1 == pytest.approx(1.284)
    assert m.power == pytest.approx(4.982 * 1.284)
    assert m.pwm == 73
    assert m.state == "RUN"
    assert m.firmware_version == "BATTERY_DISCHARGER_V1"


def test_parse_verified_ch2_frame():
    m = parse_battery_data_frame(
        b"DATA,BATTERY_DISCHARGER_V1,CH2,30000,5.001,1.201,0,81,0,RUN"
    )
    assert m.current1 == 0.0
    assert m.current2 == pytest.approx(5.001)
    assert m.voltage1 == 0.0
    assert m.voltage2 == pytest.approx(1.201)


@pytest.mark.parametrize(
    "frame",
    [
        "DEBUG,CH1,SHUNT=0.1",
        "DATA,MOTOR_BREAKIN_V3,001,1,2,3,4,5,6,7",
        "DATA,BATTERY_DISCHARGER_V1,CH3,1,5,1.2,0,50,0,RUN",
    ],
)
def test_rejects_non_battery_or_invalid_frames(frame):
    with pytest.raises(BatteryMeasurementParseError):
        parse_battery_data_frame(frame)
