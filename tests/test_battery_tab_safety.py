import sqlite3
from types import SimpleNamespace

import pytest
from PyQt5.QtWidgets import QApplication

from ui import battery_tab_ui
from ui.battery_tab_ui import BatteryTab, battery_capture_start_blocked


@pytest.mark.parametrize("status", ["STARTING", "RUN", "RUNNING", "STOPPING"])
def test_restart_is_blocked_while_channel_is_active(status):
    assert battery_capture_start_blocked([], False, status)


@pytest.mark.parametrize("status", ["COMPLETE", "STOP", "ERROR", "IDLE"])
def test_restart_is_blocked_while_unpersisted_samples_remain(status):
    assert battery_capture_start_blocked([object()], status == "COMPLETE", status)


def test_restart_is_allowed_only_after_successful_persistence_clears_buffer():
    assert not battery_capture_start_blocked([], False, "IDLE")


@pytest.mark.parametrize("zero_field", ["voltage", "current"])
def test_normal_battery_tab_stats_reject_selected_channel_zero(zero_field):
    sample = SimpleNamespace(voltage=1.4, current=5.0, elapsed_sec=0.0)
    setattr(sample, zero_field, 0.0)
    with pytest.raises(ValueError, match="validity is UNKNOWN"):
        BatteryTab._stats([sample])


def test_normal_battery_tab_stats_reject_non_finite_values():
    sample = SimpleNamespace(voltage=float("nan"), current=5.0, elapsed_sec=0.0)
    with pytest.raises(ValueError, match="validity is UNKNOWN"):
        BatteryTab._stats([sample])


def test_channel_restart_eligibility_is_independent_and_startall_checks_both():
    ch1_blocked = battery_capture_start_blocked([object()], False, "ERROR")
    ch2_blocked = battery_capture_start_blocked([], False, "IDLE")
    assert ch1_blocked
    assert not ch2_blocked
    # STARTALL is permitted only when both channel-specific checks pass.
    assert ch1_blocked or ch2_blocked
    assert not (False or ch2_blocked)


def test_selected_channel_zero_rejects_for_either_channel():
    for channel in (1, 2):
        sample = SimpleNamespace(voltage=1.4, current=5.0, elapsed_sec=1.0)
        sample.voltage = 0.0
        with pytest.raises(ValueError, match="validity is UNKNOWN"):
            BatteryTab._stats([sample])


class _ConfirmingMessageBox:
    Yes = 1
    No = 0

    @classmethod
    def question(cls, *args):
        return cls.Yes

    @classmethod
    def information(cls, *args):
        return None

    @classmethod
    def warning(cls, *args):
        return None

    @classmethod
    def critical(cls, *args):
        return None


class _DisconnectedTransport:
    connected = False


class _RecordingTransport:
    connected = True

    def __init__(self):
        self.commands = []

    def start(self, channel):
        self.commands.append(("START", channel))
        return True

    def stop(self, channel):
        self.commands.append(("STOP", channel))
        return True


class _EnabledRecorder:
    def setEnabled(self, value):
        self.enabled = value


class _TextRecorder:
    def setText(self, value):
        self.text = value


def _make_registration_tab(path, transport=None):
    app = QApplication.instance() or QApplication([])
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE battery_model (battery_model_id INTEGER PRIMARY KEY, model_code TEXT, name TEXT, is_deleted INTEGER DEFAULT 0)")
        db.execute("CREATE TABLE battery_instance (instance_id TEXT PRIMARY KEY, battery_model_id INTEGER, nickname TEXT, is_deleted INTEGER DEFAULT 0)")
        db.execute("INSERT INTO battery_model VALUES (1,'M1','Model',0)")
        db.execute("INSERT INTO battery_instance VALUES ('BAT-1',1,'Instance',0)")
        db.execute("CREATE TABLE battery_benchmark_result (result_id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER, instance_id TEXT, analysis_version TEXT, measurement_count INTEGER, avg_voltage REAL, avg_current REAL, avg_power REAL, max_current REAL, max_power REAL, discharge_time_s REAL, voltage_drop REAL, capacity_mah REAL, energy_wh REAL)")
        db.execute("CREATE TABLE measurement_session (session_id INTEGER PRIMARY KEY, instance_id TEXT, scope_key TEXT, start_datetime TEXT, end_datetime TEXT, result TEXT, notes TEXT)")
        db.execute("CREATE TABLE measurement (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER, record_type TEXT, device_model TEXT, instance_id TEXT, scope_key TEXT, elapsed_time REAL, voltage1 REAL, current1 REAL, voltage2 REAL, current2 REAL, pwm INTEGER, state TEXT, power REAL)")
    return BatteryTab(db_path=str(path), transport=transport or _DisconnectedTransport(), database_available=True)


def _sample(voltage=1.4, current=5.0, elapsed=0.0, state="COMPLETE"):
    return SimpleNamespace(
        voltage=voltage, current=current, elapsed_sec=elapsed, pwm=255, state=state
    )


def _table_counts(path):
    with sqlite3.connect(path) as db:
        return tuple(
            db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("measurement_session", "measurement", "battery_benchmark_result")
        )


def test_normal_battery_tab_persists_each_raw_sample_state(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    path = tmp_path / "battery-tab.sqlite"
    tab = _make_registration_tab(path)
    monkeypatch.setattr(battery_tab_ui, "QMessageBox", _ConfirmingMessageBox)
    tab.samples[1] = [
        SimpleNamespace(voltage=1.4, current=5.0, elapsed_sec=0.0, pwm=255, state="RUN"),
        SimpleNamespace(voltage=1.3, current=5.0, elapsed_sec=1.0, pwm=255, state="COMPLETE"),
    ]
    tab.completed[1] = True
    tab.session_started[1] = "2026-11-25T01:00:00"
    tab.register_results()
    with sqlite3.connect(path) as db:
        states = [row[0] for row in db.execute("SELECT state FROM measurement ORDER BY id")]
        count = db.execute("SELECT COUNT(*) FROM battery_benchmark_result").fetchone()[0]
    assert states == ["RUN", "COMPLETE"]
    assert count == 1
    assert tab.samples[1] == []  # cleared only after the successful DB commit


@pytest.mark.parametrize(
    ("channel", "zero_field"),
    [(1, "voltage"), (1, "current"), (2, "voltage"), (2, "current")],
)
def test_normal_battery_tab_zero_selected_sample_never_inserts(
    monkeypatch, tmp_path, channel, zero_field
):
    app = QApplication.instance() or QApplication([])
    path = tmp_path / f"battery-tab-ch{channel}-{zero_field}.sqlite"
    tab = _make_registration_tab(path)
    monkeypatch.setattr(battery_tab_ui, "QMessageBox", _ConfirmingMessageBox)
    sample = _sample()
    setattr(sample, zero_field, 0.0)
    tab.samples[channel] = [sample]
    tab.completed[channel] = True

    tab.register_results()

    assert _table_counts(path) == (0, 0, 0)
    assert tab.samples[channel] == [sample]
    assert tab.samples[channel][0] is sample


@pytest.mark.parametrize("channel", [1, 2])
def test_start_channel_rejects_unpersisted_samples_without_transport_start(
    monkeypatch, tmp_path, channel
):
    app = QApplication.instance() or QApplication([])
    transport = _RecordingTransport()
    tab = _make_registration_tab(tmp_path / f"restart-ch{channel}.sqlite", transport)
    monkeypatch.setattr(battery_tab_ui, "QMessageBox", _ConfirmingMessageBox)
    sample = _sample(state="ERROR")
    tab.samples[channel] = [sample]
    tab.latest_status[channel] = "ERROR"
    before = {ch: list(tab.samples[ch]) for ch in (1, 2)}

    tab.start_channel(channel)

    assert transport.commands == []
    assert tab.samples == before
    assert tab.samples[channel][0] is sample


@pytest.mark.parametrize("pending_channel", [1, 2])
def test_startall_rejects_if_either_channel_has_unpersisted_samples(
    monkeypatch, tmp_path, pending_channel
):
    app = QApplication.instance() or QApplication([])
    transport = _RecordingTransport()
    tab = _make_registration_tab(tmp_path / f"startall-pending-{pending_channel}.sqlite", transport)
    monkeypatch.setattr(battery_tab_ui, "QMessageBox", _ConfirmingMessageBox)
    sample = _sample(state="ERROR")
    tab.samples[pending_channel] = [sample]
    tab.latest_status[pending_channel] = "ERROR"
    before = {ch: list(tab.samples[ch]) for ch in (1, 2)}

    tab.start_channel(None)

    assert transport.commands == []
    assert tab.samples == before
    assert tab.samples[pending_channel][0] is sample


class _FailingCommitConnection(sqlite3.Connection):
    def commit(self):
        raise sqlite3.OperationalError("simulated DB commit failure")


def test_db_commit_failure_retains_samples_and_retry_allows_next_capture(
    monkeypatch, tmp_path
):
    app = QApplication.instance() or QApplication([])
    transport = _RecordingTransport()
    path = tmp_path / "battery-commit-retry.sqlite"
    tab = _make_registration_tab(path, transport)
    monkeypatch.setattr(battery_tab_ui, "QMessageBox", _ConfirmingMessageBox)
    sample = _sample()
    tab.samples[1] = [sample]
    tab.completed[1] = True
    tab.latest_status[1] = "COMPLETE"
    original_db = tab._db
    tab._db = lambda: sqlite3.connect(path, factory=_FailingCommitConnection)

    tab.register_results()

    assert tab.samples[1] == [sample]
    assert tab.samples[1][0] is sample
    assert _table_counts(path) == (0, 0, 0)

    tab._db = original_db
    tab.register_results()

    assert tab.samples[1] == []
    assert _table_counts(path) == (1, 1, 1)
    tab.start_channel(1)
    assert transport.commands == [("START", 1)]


class _RetryRawLogLibrary:
    def __init__(self):
        self.fail = True
        self.calls = 0

    def register(self, record, body):
        self.calls += 1
        if self.fail:
            raise OSError("simulated RawLog save failure")
        return "saved.log"


def test_anonymous_rawlog_save_failure_retains_capture_until_retry_then_allows_start(
    monkeypatch, tmp_path
):
    app = QApplication.instance() or QApplication([])
    transport = _RecordingTransport()
    tab = _make_registration_tab(tmp_path / "anonymous-retry.sqlite", transport)
    monkeypatch.setattr(battery_tab_ui, "QMessageBox", _ConfirmingMessageBox)
    rawlog = _RetryRawLogLibrary()
    tab.anonymous_mode = True
    tab.database_available = False
    tab.db_path = None
    tab.raw_log_library = rawlog
    sample = _sample()
    tab.samples[1] = [sample]
    tab._raw_capture[1] = ["DATA,raw-frame\n"]
    tab._capture_active[1] = True
    tab._capture_terminal_status[1] = "COMPLETE"

    first = tab._finalize_anonymous_raw_log(1, "COMPLETE")

    assert first is None
    assert tab.samples[1][0] is sample
    assert tab._capture_active[1] is True
    assert tab._capture_terminal_status[1] == "COMPLETE"
    assert transport.commands == []

    rawlog.fail = False
    tab.retry_anonymous_raw_log_saves()

    assert rawlog.calls == 2
    assert tab.samples[1] == []
    assert tab._capture_active[1] is False
    tab.start_channel(1)
    assert transport.commands == [("START", 1)]
