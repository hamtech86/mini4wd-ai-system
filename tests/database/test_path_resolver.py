from __future__ import annotations
import sqlite3
import pytest
from database.path_resolver import DB_PATH_ENV, DatabasePathError, connect_database, resolve_database_path

def make_db(path):
    with sqlite3.connect(path) as db:
        db.executescript("CREATE TABLE parent(id INTEGER PRIMARY KEY); CREATE TABLE child(id INTEGER PRIMARY KEY, parent_id INTEGER REFERENCES parent(id));")

def test_explicit_absolute_path_is_independent_of_cwd(tmp_path, monkeypatch):
    path=tmp_path/"shared.db"; make_db(path); monkeypatch.chdir(tmp_path)
    first=resolve_database_path(path); other=tmp_path/"other"; other.mkdir(); monkeypatch.chdir(other)
    assert first == resolve_database_path(path) == path.resolve()

def test_missing_configuration_fails_without_creating_database(tmp_path, monkeypatch):
    monkeypatch.delenv(DB_PATH_ENV,raising=False); monkeypatch.chdir(tmp_path)
    with pytest.raises(DatabasePathError,match="not configured"): resolve_database_path()
    assert not (tmp_path/"database"/"mini4wd.db").exists()

def test_relative_path_is_rejected_without_creating_database(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(DatabasePathError,match="must be absolute"): resolve_database_path("database/mini4wd.db")
    assert not (tmp_path/"database"/"mini4wd.db").exists()

def test_missing_absolute_path_fails_without_creating_database(tmp_path):
    path=tmp_path/"missing.db"
    with pytest.raises(DatabasePathError,match="does not exist"): connect_database(path)
    assert not path.exists()

def test_readonly_connection_rejects_writes(tmp_path):
    path=tmp_path/"readonly.db"; make_db(path); conn=connect_database(path,readonly=True)
    try:
        with pytest.raises(sqlite3.OperationalError): conn.execute("INSERT INTO parent(id) VALUES (1)")
    finally: conn.close()

def test_rw_connection_rollback_and_foreign_keys(tmp_path):
    path=tmp_path/"tx.db"; make_db(path); conn=connect_database(path)
    try:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        conn.execute("INSERT INTO parent(id) VALUES (1)"); conn.commit()
        conn.execute("INSERT INTO child(id,parent_id) VALUES (1,1)"); conn.rollback()
        assert conn.execute("SELECT COUNT(*) FROM child").fetchone()[0] == 0
        with pytest.raises(sqlite3.IntegrityError): conn.execute("INSERT INTO child(id,parent_id) VALUES (2,999)")
    finally: conn.close()

def test_required_schema_checked_without_writes(tmp_path):
    path=tmp_path/"schema.db"; make_db(path)
    with pytest.raises(DatabasePathError,match="missing tables"): resolve_database_path(path,required_tables=("motor_instance",))
    assert path.exists()
