from collections import deque

from communication.serial_controller import SerialController


class FakeSerial:
    def __init__(self, lines):
        self.lines = deque(line.encode("utf-8") for line in lines)

    @property
    def in_waiting(self):
        return sum(len(line) for line in self.lines)

    def readline(self):
        return self.lines.popleft() if self.lines else b""


def make_controller(lines):
    controller = SerialController()
    controller.serial = FakeSerial(lines)
    controller.connected = True
    return controller


def test_active_serial_controller_routes_aux_and_preserves_data_v1():
    aux = "AUX,2,sess_1,7,WINDING,FWD,0,MEASURE,A0,514,123456\r\n"
    data = ",".join(["DATA"] + ["0"] * 25) + "\r\n"
    controller = make_controller([aux, data])

    latest = controller.read_measurement()
    records = controller.drain_aux_records()

    assert latest == data.strip()
    assert len(records) == 1
    assert records[0].channel == "A0"
    assert records[0].adc_raw == 514
    assert records[0].timestamp_us == 123456
    assert controller.drain_aux_parse_errors() == []
    assert controller.raw_log == aux + data


def test_active_serial_controller_retains_invalid_aux_and_reports_error():
    invalid = "AUX,2,sess_1,7,WINDING,FWD,0,MEASURE,A2,514,123456\r\n"
    controller = make_controller([invalid])

    assert controller.read_measurement() is None
    assert controller.drain_aux_records() == []
    errors = controller.drain_aux_parse_errors()

    assert len(errors) == 1
    assert errors[0]["raw_line"] == invalid.rstrip("\r\n")
    assert "invalid channel" in errors[0]["error"]
    assert controller.raw_log == invalid


def test_reset_raw_log_clears_aux_queues():
    controller = make_controller([])
    controller.aux_records.append(object())
    controller.aux_parse_errors.append({"raw_line": "bad", "error": "bad"})

    controller.reset_raw_log()

    assert controller.drain_aux_records() == []
    assert controller.drain_aux_parse_errors() == []
