from communication.raw_log_collector import RawLogCollector


def test_raw_log_collector_preserves_received_lines():
    collector = RawLogCollector()
    first = "INFO,TYPE=MOTOR\r\n"
    second = "DEBUG,STATE=RUN\n"
    third = "DATA,MOTOR_BREAKIN_V3,MOTOR-000001,100,1,2,3\n"

    collector.append(first)
    collector.append(second)
    collector.append(third)

    assert collector.has_data
    assert collector.snapshot() == first + second + third
    assert collector.raw_text == first + second + third


def test_raw_log_collector_reset_starts_new_capture():
    collector = RawLogCollector()
    collector.append("old\n")

    collector.reset()

    assert not collector.has_data
    assert collector.snapshot() == ""
