import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QWidget

from battery_system.serial import BatterySerial
from raw_log_library import RawLogLibrary
from ui.battery_tab_ui import BatteryTab


class FakeBatteryTransport:
    def __init__(self):
        self.connected = True
        self.commands = []
        self.lines = []

    def start(self, channel=None):
        self.commands.append(("START", channel))
        return True

    def stop(self, channel=None):
        self.commands.append(("STOP", channel))
        return True

    def read_lines(self):
        lines, self.lines = self.lines, []
        return lines

    parse_data = staticmethod(BatterySerial.parse_data)


def qapp():
    return QApplication.instance() or QApplication([])


def test_battery_anonymous_mode_allows_instance_free_channel_and_saves_rawlog(tmp_path):
    qapp()
    transport = FakeBatteryTransport()
    library = RawLogLibrary(tmp_path / "raw_logs")
    tab = BatteryTab(
        db_path=None,
        transport=transport,
        database_available=False,
        raw_log_library=library,
    )
    try:
        tab.set_connected(True)
        assert tab.anonymous_mode
        assert tab.ch1_instance.currentData() is None
        assert tab.ch2_instance.currentData() is None
        assert tab.ch1_start.isEnabled()
        assert tab.ch2_start.isEnabled()
        assert not tab.register_result_button.isEnabled()

        tab.start_channel(1)
        assert transport.commands == [("START", 1)]
        assert tab._capture_active[1]

        status = "STATUS,RUN,IDLE\r\n"
        complete = "DATA,0,CH1,1000,4.2,1.20,0,255,0,COMPLETE\r\n"
        transport.lines.extend([status, complete])
        tab.poll_serial()

        assert not tab._capture_active[1]
        assert tab.completed[1]
        assert tab.local_raw_log_ids[1] == "BATTERY-000001"
        record, _, _ = library.get("BATTERY-000001")
        assert record.device_type == "BATTERY"
        assert record.device_instance_id is None
        assert record.battery_id is None
        assert record.channel == "CH1"
        assert record.measurement_session_id is None
        assert "terminal_status=COMPLETE" in record.notes
        assert library.read_raw("BATTERY-000001") == status + complete
    finally:
        tab.close()


def test_battery_anonymous_mode_preserves_incomplete_rawlog_on_disconnect(tmp_path):
    qapp()
    transport = FakeBatteryTransport()
    library = RawLogLibrary(tmp_path / "raw_logs")
    tab = BatteryTab(
        db_path=None,
        transport=transport,
        database_available=False,
        raw_log_library=library,
    )
    try:
        tab.set_connected(True)
        tab.start_channel(2)
        raw_line = "DATA,0,CH2,250,4.0,1.31,0,255,0,RUN\r\n"
        transport.lines.append(raw_line)
        tab.poll_serial()
        tab.set_connected(False)

        assert not tab.completed[2]
        assert not tab._capture_active[2]
        assert tab.local_raw_log_ids[2] == "BATTERY-000001"
        record, _, _ = library.get("BATTERY-000001")
        assert record.channel == "CH2"
        assert "terminal_status=DISCONNECTED_INCOMPLETE" in record.notes
        assert library.read_raw("BATTERY-000001") == raw_line
    finally:
        tab.close()


def test_battery_serial_read_lines_preserves_original_line_endings():
    class FakePort:
        def __init__(self):
            self.lines = [b"STATUS,RUN,IDLE\r\n", b""]

        @property
        def in_waiting(self):
            return len(self.lines)

        def readline(self):
            return self.lines.pop(0)

    transport = BatterySerial()
    transport.serial = FakePort()
    transport.connected = True

    assert transport.read_lines() == ["STATUS,RUN,IDLE\r\n"]


def test_mainui_starts_in_anonymous_mode_without_database(monkeypatch):
    import app.main as main_app
    import ui.main_window as base_ui

    class FakeBatteryTab(QWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(kwargs.get("parent"))

        def set_connected(self, connected):
            self.connected = connected

    def unavailable(**kwargs):
        raise FileNotFoundError("database intentionally absent in test")

    monkeypatch.setattr(base_ui, "resolve_database_path", unavailable)
    monkeypatch.setattr(main_app, "BatteryTab", FakeBatteryTab)
    app = qapp()
    window = main_app.MainWindow({
        "breakin_controller": None,
        "serial_controller": None,
        "battery_serial_controller": None,
    })
    try:
        assert not window.database_available
        assert window.db_path is None
        assert "ANONYMOUS MODE" in window.database_mode_status.text()
        assert window.instance.currentData() is None
        assert "ANONYMOUS MODE" in window.instance.currentText()
        assert not window.manager.isEnabled()
        assert not window.update_db.isEnabled()
        assert not window.raw_log.isEnabled()
        assert window.motor_connect.isEnabled()
        assert window.battery_connect.isEnabled()
        assert window.emergency_stop_fixed.isEnabled()
    finally:
        window.close()



def test_mainui_starts_anonymous_mode_for_incomplete_schema_without_migrating_it(
    monkeypatch, tmp_path
):
    import sqlite3
    import app.main as main_app
    from database.path_resolver import DB_PATH_ENV

    class FakeBatteryTab(QWidget):
        def __init__(self, *args, **kwargs):
            super().__init__(kwargs.get("parent"))

        def set_connected(self, connected):
            self.connected = connected

    qapp()
    database = tmp_path / "incomplete.db"
    sqlite3.connect(database).close()
    monkeypatch.setenv(DB_PATH_ENV, str(database))
    monkeypatch.setattr(main_app, "BatteryTab", FakeBatteryTab)

    window = main_app.MainWindow({
        "breakin_controller": None,
        "serial_controller": None,
        "battery_serial_controller": None,
    })
    try:
        assert not window.database_available
        assert "missing tables" in window.database_error
        assert "ANONYMOUS MODE" in window.database_mode_status.text()
    finally:
        window.close()

    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as db:
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    assert tables == []


def test_battery_anonymous_mode_simultaneous_channels_save_separate_rawlogs(tmp_path):
    qapp()
    transport = FakeBatteryTransport()
    library = RawLogLibrary(tmp_path / "raw_logs")
    tab = BatteryTab(
        db_path=None,
        transport=transport,
        database_available=False,
        raw_log_library=library,
    )
    try:
        tab.set_connected(True)
        tab.start_channel(None)
        assert transport.commands == [("START", None)]
        assert tab._capture_active == {1: True, 2: True}

        transport.lines.extend([
            "STATUS,RUN,RUN\r\n",
            "DATA,0,CH1,250,4.2,1.30,0,255,0,RUN\r\n",
            "DATA,0,CH2,250,4.1,1.29,0,255,0,RUN\r\n",
            "STATUS,COMPLETE,COMPLETE\r\n",
        ])
        tab.poll_serial()

        assert tab.completed == {1: True, 2: True}
        assert not tab._capture_active[1]
        assert not tab._capture_active[2]
        ch1, _, _ = library.get(tab.local_raw_log_ids[1])
        ch2, _, _ = library.get(tab.local_raw_log_ids[2])
        assert ch1.channel == "CH1"
        assert ch2.channel == "CH2"
        assert "CH1" in library.read_raw(ch1.log_id)
        assert "CH2" not in library.read_raw(ch1.log_id)
        assert "CH2" in library.read_raw(ch2.log_id)
        assert "CH1" not in library.read_raw(ch2.log_id)
    finally:
        tab.close()


def test_anonymous_rawlog_save_failure_remains_retryable(tmp_path):
    class FlakyLibrary:
        def __init__(self, root):
            self.library = RawLogLibrary(root)
            self.fail_once = True

        def register(self, record, body):
            if self.fail_once:
                self.fail_once = False
                raise OSError("simulated disk write failure")
            return self.library.register(record, body)

        def __getattr__(self, name):
            return getattr(self.library, name)

    qapp()
    transport = FakeBatteryTransport()
    library = FlakyLibrary(tmp_path / "raw_logs")
    tab = BatteryTab(
        db_path=None,
        transport=transport,
        database_available=False,
        raw_log_library=library,
    )
    try:
        tab.set_connected(True)
        tab.start_channel(1)
        transport.lines.append("DATA,0,CH1,250,4.2,1.30,0,255,0,RUN\r\n")
        tab.poll_serial()
        tab._status(1, "COMPLETE")

        assert tab._capture_active[1]
        assert tab._capture_terminal_status[1] == "COMPLETE"
        assert tab.retry_raw_log_button.isEnabled()
        assert library.library.list_logs("BATTERY") == []

        tab.retry_anonymous_raw_log_saves()

        assert not tab._capture_active[1]
        assert tab.local_raw_log_ids[1] == "BATTERY-000001"
        assert not tab.retry_raw_log_button.isEnabled()
        assert library.read_raw("BATTERY-000001").endswith("RUN\r\n")
    finally:
        tab.close()



def test_battery_operation_tab_scrolls_to_start_stop_controls_on_small_window(tmp_path):
    from PyQt5.QtCore import QPoint
    from PyQt5.QtWidgets import QScrollArea

    qapp()
    tab = BatteryTab(
        db_path=None,
        transport=FakeBatteryTransport(),
        database_available=False,
        raw_log_library=RawLogLibrary(tmp_path / "raw_logs"),
    )
    try:
        tab.resize(420, 260)
        tab.show()
        tab.set_connected(True)
        scroll = tab.findChild(QScrollArea)
        assert scroll is tab.operation_scroll_area
        assert scroll.widgetResizable()
        assert scroll.widget() is not None
        assert tab.ch1_start.isEnabled()
        assert tab.ch2_start.isEnabled()
        assert tab.all_start.isEnabled()

        # The operation page exceeds the deliberately small viewport. Scrolling
        # must bring the final channel's controls into the visible viewport.
        tab.application = QApplication.instance()
        tab.application.processEvents()
        assert scroll.verticalScrollBar().maximum() > 0
        scroll.ensureWidgetVisible(tab.ch2_stop)
        tab.application.processEvents()
        assert scroll.verticalScrollBar().value() > 0
        button_top_left = tab.ch2_stop.mapTo(scroll.viewport(), QPoint(0, 0))
        assert scroll.viewport().rect().contains(button_top_left)
    finally:
        tab.close()
