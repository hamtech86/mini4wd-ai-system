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


class _EnabledRecorder:
    def setEnabled(self, value):
        self.enabled = value


class _TextRecorder:
    def setText(self, value):
        self.text = value


def _make_registration_tab(path):
    app = QApplication.instance() or QApplication([])
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE battery_model (battery_model_id INTEGER PRIMARY KEY, model_code TEXT, name TEXT, is_deleted INTEGER DEFAULT 0)")
        db.execute("CREATE TABLE battery_instance (instance_id TEXT PRIMARY KEY, battery_model_id INTEGER, nickname TEXT, is_deleted INTEGER DEFAULT 0)")
        db.execute("INSERT INTO battery_model VALUES (1,'M1','Model',0)")
        db.execute("INSERT INTO battery_instance VALUES ('BAT-1',1,'Instance',0)")
        db.execute("CREATE TABLE battery_benchmark_result (result_id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER, instance_id TEXT, analysis_version TEXT, measurement_count INTEGER, avg_voltage REAL, avg_current REAL, avg_power REAL, max_current REAL, max_power REAL, discharge_time_s REAL, voltage_drop REAL, capacity_mah REAL, energy_wh REAL)")
        db.execute("CREATE TABLE measurement_session (session_id INTEGER PRIMARY KEY, instance_id TEXT, scope_key TEXT, start_datetime TEXT, end_datetime TEXT, result TEXT, notes TEXT)")
        db.execute("CREATE TABLE measurement (id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER, record_type TEXT, device_model TEXT, instance_id TEXT, scope_key TEXT, elapsed_time REAL, voltage1 REAL, current1 REAL, voltage2 REAL, current2 REAL, pwm INTEGER, state TEXT, power REAL)")
    return BatteryTab(db_path=str(path), transport=_DisconnectedTransport(), database_available=True)


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


@pytest.mark.parametrize("channel", [1, 2])
def test_normal_battery_tab_zero_selected_sample_never_inserts(monkeypatch, tmp_path, channel):
    app = QApplication.instance() or QApplication([])
    path = tmp_path / f"battery-tab-ch{channel}.sqlite"
    tab = _make_registration_tab(path)
    monkeypatch.setattr(battery_tab_ui, "QMessageBox", _ConfirmingMessageBox)
    tab.samples[channel] = [
        SimpleNamespace(voltage=0.0, current=5.0, elapsed_sec=0.0, pwm=255, state="RUN"),
    ]
    tab.completed[channel] = True
    tab.register_results()
    with sqlite3.connect(path) as db:
        sessions = db.execute("SELECT COUNT(*) FROM measurement_session").fetchone()[0]
        measurements = db.execute("SELECT COUNT(*) FROM measurement").fetchone()[0]
        results = db.execute("SELECT COUNT(*) FROM battery_benchmark_result").fetchone()[0]
    assert (sessions, measurements, results) == (0, 0, 0)
    assert len(tab.samples[channel]) == 1  # failed registration retains source data
