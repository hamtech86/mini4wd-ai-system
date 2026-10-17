"""Fail-closed shared SQLite path and connection helpers."""
from __future__ import annotations
import os
import sqlite3
import subprocess
from contextlib import closing
from pathlib import Path
from typing import Iterable

DB_PATH_ENV = "MINI4WD_DB_PATH"


class DatabasePathError(RuntimeError):
    """Raised when a database target cannot be resolved safely."""


def configure_shared_database_path(project_root: str | os.PathLike[str]) -> Path:
    """Set one default DB path shared by all Git worktrees of this repository.

    An explicit MINI4WD_DB_PATH always wins. Otherwise, locate the common Git
    directory and use the main checkout's database/mini4wd.db. In a source
    archive without Git metadata, use project_root/database/mini4wd.db.
    This function only configures a path; it never creates or opens a DB.
    """
    configured = os.environ.get(DB_PATH_ENV)
    if configured is not None and configured.strip():
        return Path(configured).expanduser()

    root = Path(project_root).expanduser().resolve()
    repository_root = root
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
            timeout=3,
        )
        common_dir = Path(result.stdout.strip()).expanduser()
        if not common_dir.is_absolute():
            common_dir = (root / common_dir).resolve()
        else:
            common_dir = common_dir.resolve()
        if common_dir.name == ".git":
            repository_root = common_dir.parent
    except (OSError, subprocess.SubprocessError):
        # A source archive may not contain Git metadata; do not guess elsewhere.
        repository_root = root

    path = repository_root / "database" / "mini4wd.db"
    os.environ[DB_PATH_ENV] = str(path)
    return path


def resolve_database_path(db_path: str | os.PathLike[str] | None = None, *, required_tables: Iterable[str] = ()) -> Path:
    """Require an explicitly configured absolute path to an existing database."""
    raw = db_path if db_path is not None else os.environ.get(DB_PATH_ENV)
    if raw is None or not str(raw).strip():
        raise DatabasePathError(f"Database path is not configured; set {DB_PATH_ENV} to an absolute existing file path")
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        raise DatabasePathError(f"Database path must be absolute; relative paths are rejected: {candidate}")
    try:
        path = candidate.resolve(strict=True)
    except (FileNotFoundError, OSError) as exc:
        raise DatabasePathError(f"Database file does not exist or cannot be resolved: {candidate}") from exc
    if not path.is_file():
        raise DatabasePathError(f"Database path is not a regular file: {path}")
    required = tuple(required_tables)
    if required:
        try:
            with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=5.0)) as conn:
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        except sqlite3.Error as exc:
            raise DatabasePathError(f"Database is not readable: {path}: {exc}") from exc
        missing = sorted(set(required) - tables)
        if missing:
            raise DatabasePathError(f"Database schema is incomplete at {path}; missing tables: {', '.join(missing)}")
    return path


def connect_database(db_path: str | os.PathLike[str] | None = None, *, readonly: bool = False, timeout: float = 5.0, required_tables: Iterable[str] = ()) -> sqlite3.Connection:
    """Open an existing database in mode=ro or mode=rw; never create implicitly."""
    path = resolve_database_path(db_path, required_tables=required_tables)
    mode = "ro" if readonly else "rw"
    conn = sqlite3.connect(path.as_uri() + f"?mode={mode}", uri=True, timeout=timeout)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
