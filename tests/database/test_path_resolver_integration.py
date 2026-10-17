from __future__ import annotations

import ast
import os
import sqlite3
from pathlib import Path

import pytest

from database.path_resolver import DB_PATH_ENV, DatabasePathError


@pytest.fixture(scope="session")
def qapp():
    """Qt UI constructors are exercised offscreen; no serial/device startup occurs."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PyQt5")
    from PyQt5.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def test_database_manager_requires_explicit_existing_database(tmp_path, monkeypatch):
    from database.manager.database_manager import DatabaseManager

    monkeypatch.delenv(DB_PATH_ENV, raising=False)
    with pytest.raises(DatabasePathError, match="not configured"):
        DatabaseManager()
    missing = tmp_path / "missing.db"
    with pytest.raises(DatabasePathError, match="does not exist"):
        DatabaseManager(missing)
    assert not missing.exists()


def test_database_connection_rejects_relative_and_missing_paths(tmp_path, monkeypatch):
    from database.manager.connection import DatabaseConnection

    monkeypatch.chdir(tmp_path)
    with pytest.raises(DatabasePathError, match="must be absolute"):
        DatabaseConnection("database/mini4wd.db")
    missing = tmp_path / "missing.db"
    with pytest.raises(DatabasePathError, match="does not exist"):
        DatabaseConnection(missing)
    assert not (tmp_path / "database" / "mini4wd.db").exists()
    assert not missing.exists()


def test_database_manager_and_connection_use_the_explicit_temp_database(tmp_path, monkeypatch):
    from database.manager.connection import DatabaseConnection
    from database.manager.database_manager import DatabaseManager

    path = tmp_path / "isolated.db"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY)")
    monkeypatch.delenv(DB_PATH_ENV, raising=False)

    manager = DatabaseManager(path)
    conn = manager.connect()
    conn.execute("INSERT INTO sample DEFAULT VALUES")
    manager.commit()
    manager.close()

    wrapper = DatabaseConnection(path)
    wrapper.connect()
    assert wrapper.execute("SELECT COUNT(*) FROM sample").fetchone()[0] == 1
    wrapper.close()
    assert path.exists()


def test_main_window_uses_shared_checkout_database_when_path_is_unset(qapp, monkeypatch, tmp_path):
    from ui.main_window import MainWindow

    root = Path(__file__).resolve().parents[2]
    expected = (root / "database" / "mini4wd.db").resolve()
    monkeypatch.delenv(DB_PATH_ENV, raising=False)
    monkeypatch.chdir(tmp_path)

    window = MainWindow(context={})
    try:
        assert Path(window.db_path).resolve() == expected
        assert os.environ[DB_PATH_ENV] == str(root / "database" / "mini4wd.db")
        assert not (tmp_path / "database" / "mini4wd.db").exists()
    finally:
        window.close()


@pytest.mark.parametrize(
    "module_name,class_name,args",
    [
        ("ui.battery_tab_ui", "BatteryTab", ("missing.db",)),
        ("ui.battery_database_ui", "BatteryDatabaseDialog", ("missing.db",)),
    ],
)
def test_battery_uis_reject_missing_database_without_creating_it(
    qapp, monkeypatch, tmp_path, module_name, class_name, args
):
    import importlib

    monkeypatch.delenv(DB_PATH_ENV, raising=False)
    missing = tmp_path / args[0]
    cls = getattr(importlib.import_module(module_name), class_name)
    with pytest.raises(DatabasePathError, match="does not exist"):
        cls(missing)
    assert not missing.exists()


def test_motor_instance_ui_path_lookup_fails_closed(monkeypatch):
    from ui.motor_instance_ui import MotorInstanceUI

    monkeypatch.delenv(DB_PATH_ENV, raising=False)
    instance = object.__new__(MotorInstanceUI)
    with pytest.raises(DatabasePathError, match="not configured"):
        instance._database_path()


@pytest.mark.parametrize(
    "module_name,class_name",
    [
        ("motor_system.python.ui.motor_manager_ui", "MotorManagerUI"),
        ("ui.raw_log_database_manager", "RawLogDatabaseManager"),
    ],
)
def test_motor_and_rawlog_managers_fail_closed_before_db_connection(
    qapp, monkeypatch, module_name, class_name
):
    import importlib

    monkeypatch.delenv(DB_PATH_ENV, raising=False)
    cls = getattr(importlib.import_module(module_name), class_name)
    with pytest.raises(DatabasePathError, match="not configured"):
        cls()


@pytest.mark.parametrize(
    "module_name,class_name",
    [
        ("motor_system.python.ui.motor_manager_ui", "MotorManagerUI"),
        ("ui.raw_log_database_manager", "RawLogDatabaseManager"),
    ],
)
def test_motor_and_rawlog_managers_reject_incomplete_existing_schema(
    qapp, monkeypatch, tmp_path, module_name, class_name
):
    import importlib

    path = tmp_path / "incomplete.db"
    sqlite3.connect(path).close()
    monkeypatch.setenv(DB_PATH_ENV, str(path))
    cls = getattr(importlib.import_module(module_name), class_name)

    with pytest.raises(DatabasePathError, match="missing tables"):
        cls()

    # Validation is read-only: an incomplete existing database is not migrated.
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        tables = db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    assert tables == []


@pytest.mark.parametrize(
    "module_name,function_name",
    [
        ("database.tools.migrate_battery_benchmark_v2", "main"),
        ("database.tools.verify_battery_benchmark_v2", "main"),
        ("database.tools.reset_battery_data", "reset"),
    ],
)
def test_database_tools_reject_missing_database_without_creating_it(
    tmp_path, monkeypatch, module_name, function_name
):
    import importlib

    monkeypatch.delenv(DB_PATH_ENV, raising=False)
    missing = tmp_path / "not-created.db"
    function = getattr(importlib.import_module(module_name), function_name)
    with pytest.raises(DatabasePathError, match="does not exist"):
        function(missing)
    assert not missing.exists()


def test_normal_startup_does_not_call_migration_or_create_schema():
    root = Path(__file__).resolve().parents[2]
    startup_files = [
        root / "app" / "main.py",
        root / "ui" / "main_window.py",
        root / "ui" / "battery_tab_ui.py",
        root / "ui" / "battery_database_ui.py",
    ]
    for path in startup_files:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        names = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
        }
        calls = {
            node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        assert "Migration" not in names, f"unexpected Migration reference in {path}"
        assert "executescript" not in calls, f"startup schema SQL found in {path}"
    battery_db_ui = (root / "ui" / "battery_database_ui.py").read_text(encoding="utf-8")
    assert "_ensure_schema" not in battery_db_ui
