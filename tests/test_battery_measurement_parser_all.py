from measurement.battery_measurement_parser import parse_battery_data_frame


def test_startall_produces_independent_channel_measurements():
    ch1 = parse_battery_data_frame(
        "DATA,BATTERY_DISCHARGER_V1,CH1,100,5.000,1.300,0,70,0,RUN"
    )
    ch2 = parse_battery_data_frame(
        "DATA,BATTERY_DISCHARGER_V1,CH2,100,5.100,1.290,0,71,0,RUN"
    )

    assert ch1.instance_id == "CH1"
    assert ch2.instance_id == "CH2"
    assert ch1.current2 == 0.0
    assert ch2.current1 == 0.0
    assert ch1.power != ch2.power
