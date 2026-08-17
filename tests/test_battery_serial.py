from battery_system.serial import BatterySerial


def test_parse_current_battery_data_frame():
    sample = BatterySerial.parse_data(
        "DATA,BATTERY_DISCHARGER_V1,CH1,1234,4.812,1.203,0,87,0,RUN"
    )
    assert sample is not None
    assert sample.channel == 1
    assert sample.elapsed_sec == 1.234
    assert sample.current == 4.812
    assert sample.voltage == 1.203
    assert sample.pwm == 87
    assert sample.state == "RUN"


def test_debug_is_not_measurement_data():
    assert BatterySerial.parse_data("DEBUG,CH1,SHUNT=0.123") is None
