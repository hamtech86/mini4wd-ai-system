from collections import deque

from communication.serial_manager import SerialReader


class FakeCollector:
    def __init__(self):
        self.lines = []

    def append(self, line):
        self.lines.append(line)


class FakePort:
    def __init__(self, lines):
        self.lines = deque(line.encode("utf-8") for line in lines)
        self.is_open = True
        self.reader = None

    @property
    def in_waiting(self):
        return sum(len(line) for line in self.lines)

    def readline(self):
        line = self.lines.popleft()
        if not self.lines:
            self.reader.running = False
        return line


def test_aux_is_dispatched_separately_and_data_contract_is_unchanged():
    aux_line = "AUX,2,sess_1,7,WINDING,FWD,0,MEASURE,A0,514,123456\\r\\n"
    data_line = ",".join(["DATA"] + ["0"] * 25) + "\\r\\n"
    collector = FakeCollector()
    port = FakePort([aux_line, data_line])
    reader = SerialReader(port, collector)
    port.reader = reader
    received = []
    aux_received = []
    errors = []
    reader.received.connect(received.append)
    reader.aux_received.connect(aux_received.append)
    reader.error.connect(errors.append)

    reader.run()

    assert len(aux_received) == 1
    assert aux_received[0].channel == "A0"
    assert aux_received[0].adc_raw == 514
    assert aux_received[0].timestamp_us == 123456
    assert len(received) == 1
    assert received[0]["record_type"] == "DATA"
    assert len(received[0]) == 26
    assert errors == []
    assert collector.lines == [aux_line, data_line]


def test_invalid_aux_is_preserved_and_reported_without_becoming_data():
    invalid = "AUX,2,sess_1,7,WINDING,FWD,0,MEASURE,A2,514,123456\\r\\n"
    data_line = ",".join(["DATA"] + ["0"] * 25) + "\\r\\n"
    collector = FakeCollector()
    port = FakePort([invalid, data_line])
    reader = SerialReader(port, collector)
    port.reader = reader
    received = []
    aux_received = []
    errors = []
    reader.received.connect(received.append)
    reader.aux_received.connect(aux_received.append)
    reader.error.connect(errors.append)

    reader.run()

    assert aux_received == []
    assert len(received) == 1
    assert received[0]["record_type"] == "DATA"
    assert len(errors) == 1
    assert errors[0].startswith("Invalid AUX record:")
    assert collector.lines == [invalid, data_line]
