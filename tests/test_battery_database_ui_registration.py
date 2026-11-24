import sqlite3
from types import SimpleNamespace

import pytest

from ui import battery_database_ui


class ValueWidget:
    def __init__(self, value=1):
        self._value = value

    def value(self):
        return self._value


class TextWidget:
    def __init__(self, value="battery-benchmark-v2"):
        self._value = value

    def text(self):
        return self._value


class ConfirmWidget:
    def isChecked(self):
        return True


class StatusWidget:
    def __init__(self):
        self.value = ""

    def setText(self, value):
        self.value = value


class MessageBoxRecorder:
    warnings = []
    criticals = []
    infos = []

    @classmethod
    def warning(cls, *args):
        cls.warnings.append(args)

    @classmethod
    def critical(cls, *args):
        cls.criticals.append(args)

    @classmethod
    def information(cls, *args):
        cls.infos.append(args)


def create_database(path):
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE measurement_session (
            session_id TEXT PRIMARY KEY, scope_key TEXT, instance_id TEXT,
            result TEXT, end_time TEXT
        )""")
        db.execute("""CREATE TABLE measurement (
            id INTEGER PRIMARY KEY, session_id TEXT, scope_key TEXT,
            elapsed_time REAL, voltage1 REAL, voltage2 REAL,
            current1 REAL, current2 REAL, state TEXT
        )""")
        db.execute("""CREATE TABLE battery_benchmark_result (
            session_id TEXT, instance_id TEXT, analysis_version TEXT,
            measurement_count INTEGER, avg_voltage REAL, avg_current REAL,
            avg_power REAL, max_current REAL, max_power REAL,
            discharge_time_s REAL, voltage_drop REAL, capacity_mah REAL,
            energy_wh REAL
        )""")
        db.execute(
            "INSERT INTO measurement_session VALUES ('S1','BATTERY:CH1','BAT-001','COMPLETE','2026-11-24T10:00:00')"
        )
        db.executemany(
            "INSERT INTO measurement VALUES (?,?,?,?,?,?,?,?,?)",
            [
                (1, "S1", "BATTERY:CH1", 0.0, 1.4, 0.0, 5.0, 0.0, "RUN"),
                (2, "S1", "BATTERY:CH1", 1.0, 1.3, 0.0, 5.0, 0.0, "COMPLETE"),
            ],
        )


def make_dialog(path):
    dialog = SimpleNamespace()
    dialog._db = lambda: sqlite3.connect(path)
    dialog.session = SimpleNamespace(currentData=lambda: "S1", currentText=lambda: "S1")
    dialog.result_instance = SimpleNamespace(currentData=lambda: "BAT-001")
    dialog._channel_identity = "CH1"  # identity observed during UI load; DB is re-read at registration
    dialog.version = TextWidget()
    dialog.count = ValueWidget(2)
    dialog.avg_v = ValueWidget(1.35)
    dialog.avg_i = ValueWidget(5.0)
    dialog.avg_p = ValueWidget(6.75)
    dialog.max_i = ValueWidget(5.0)
    dialog.max_p = ValueWidget(7.0)
    dialog.duration = ValueWidget(1.0)
    dialog.drop = ValueWidget(0.1)
    dialog.cap = ValueWidget(1.0)
    dialog.energy = ValueWidget(0.002)
    dialog.quality = ConfirmWidget()
    dialog.operator = ConfirmWidget()
    dialog.status = StatusWidget()
    return dialog


@pytest.fixture(autouse=True)
def message_box_recorder(monkeypatch):
    MessageBoxRecorder.warnings = []
    MessageBoxRecorder.criticals = []
    MessageBoxRecorder.infos = []
    monkeypatch.setattr(battery_database_ui, "QMessageBox", MessageBoxRecorder)


def test_register_result_revalidates_scope_and_inserts_on_exact_match(tmp_path):
    path = tmp_path / "battery.sqlite"
    create_database(path)
    dialog = make_dialog(path)

    battery_database_ui.BatteryDatabaseDialog._register_result(dialog)

    with sqlite3.connect(path) as db:
        rows = db.execute("SELECT session_id,instance_id FROM battery_benchmark_result").fetchall()
    assert rows == [("S1", "BAT-001")]
    assert dialog.status.value.startswith("REGISTERED:")
    assert len(MessageBoxRecorder.infos) == 1
    assert not MessageBoxRecorder.criticals


@pytest.mark.parametrize("new_scope", [None, "UNKNOWN", "BATTERY:CH2"])
def test_register_result_rejects_scope_changed_after_ui_load_without_insert(tmp_path, new_scope):
    path = tmp_path / "battery.sqlite"
    create_database(path)
    # Simulate a persisted change after the UI initially loaded and cached CH1.
    with sqlite3.connect(path) as db:
        db.execute("UPDATE measurement SET scope_key=? WHERE id=2", (new_scope,))
    dialog = make_dialog(path)

    battery_database_ui.BatteryDatabaseDialog._register_result(dialog)

    with sqlite3.connect(path) as db:
        count = db.execute("SELECT COUNT(*) FROM battery_benchmark_result").fetchone()[0]
    assert count == 0
    assert dialog.status.value.startswith("NOT REGISTERED:")
    assert len(MessageBoxRecorder.criticals) == 1
    assert not MessageBoxRecorder.infos


def test_register_result_rejects_session_scope_changed_after_ui_load_without_insert(tmp_path):
    path = tmp_path / "battery.sqlite"
    create_database(path)
    with sqlite3.connect(path) as db:
        db.execute("UPDATE measurement_session SET scope_key='BATTERY:CH2' WHERE session_id='S1'")
    dialog = make_dialog(path)

    battery_database_ui.BatteryDatabaseDialog._register_result(dialog)

    with sqlite3.connect(path) as db:
        count = db.execute("SELECT COUNT(*) FROM battery_benchmark_result").fetchone()[0]
    assert count == 0
    assert len(MessageBoxRecorder.criticals) == 1
