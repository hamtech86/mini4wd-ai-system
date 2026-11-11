"""Append-only filesystem storage for independent RawLog v2 packages.

RawLog v1 files are outside this store and are never migrated or rewritten.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import threading
from typing import Mapping

from raw_log_library.v2_schema import (
    SCHEMA_ID,
    RawLogV2ValidationError,
    validate_record,
)


_LOG_ID_RE = re.compile(r"^(?:MOTOR|BATTERY)-[A-Za-z0-9_-]+$")
_FINAL_STATUSES = {"COMPLETE", "STOPPED", "INTERRUPTED", "FAULTED"}


class RawLogV2StoreError(ValueError):
    """Raised when a RawLog v2 package cannot be safely stored."""


class RawLogV2Store:
    """Append-only JSONL package store with a separately updated manifest."""

    def __init__(self, root: str | Path = "data/raw_logs_v2") -> None:
        self.root = Path(root)
        self._lock = threading.RLock()
        self._manifest = None
        self._package_dir = None
        self._record_ids: set[str] = set()
        self._last_sequence = -1

    @property
    def active(self) -> bool:
        return self._manifest is not None

    @property
    def log_id(self) -> str | None:
        return None if self._manifest is None else self._manifest["log_id"]

    def create(self, manifest: Mapping) -> Path:
        """Create a new package. Existing package IDs are never overwritten."""
        with self._lock:
            if self.active:
                raise RawLogV2StoreError("a RawLog v2 package is already active")
            if not isinstance(manifest, Mapping):
                raise RawLogV2StoreError("manifest must be an object")
            required = {"schema", "log_id", "measurement_session_id", "status", "started_at"}
            missing = sorted(required - set(manifest))
            if missing:
                raise RawLogV2StoreError("manifest missing fields: " + ", ".join(missing))
            if manifest["schema"] != SCHEMA_ID:
                raise RawLogV2StoreError("manifest schema mismatch")
            log_id = manifest["log_id"]
            if not isinstance(log_id, str) or not _LOG_ID_RE.fullmatch(log_id):
                raise RawLogV2StoreError("invalid log_id")
            if not isinstance(manifest["measurement_session_id"], str) or not manifest["measurement_session_id"].strip():
                raise RawLogV2StoreError("measurement_session_id must be non-empty")
            if manifest["status"] != "STARTED":
                raise RawLogV2StoreError("new package status must be STARTED")
            if not isinstance(manifest["started_at"], str) or not manifest["started_at"].strip():
                raise RawLogV2StoreError("started_at must be non-empty")

            package_dir = self.root / log_id
            package_dir.mkdir(parents=True, exist_ok=False)
            self._manifest = dict(manifest)
            self._manifest.setdefault("ended_at", None)
            self._manifest.setdefault("final_reason", None)
            self._manifest["record_count"] = 0
            self._manifest["record_type_counts"] = {}
            self._package_dir = package_dir
            self._record_ids.clear()
            self._last_sequence = -1
            try:
                (package_dir / "records.jsonl").touch(exist_ok=False)
                self._write_manifest()
            except Exception:
                self._manifest = None
                self._package_dir = None
                raise
            return package_dir

    def append(self, record: Mapping) -> None:
        """Validate and append one immutable v2 record."""
        with self._lock:
            if not self.active:
                raise RawLogV2StoreError("no active RawLog v2 package")
            try:
                validate_record(record)
            except RawLogV2ValidationError as exc:
                raise RawLogV2StoreError(str(exc)) from exc

            if record["log_id"] != self._manifest["log_id"]:
                raise RawLogV2StoreError("record log_id does not match active package")
            if record["measurement_session_id"] != self._manifest["measurement_session_id"]:
                raise RawLogV2StoreError("record measurement_session_id does not match active package")
            if record["record_id"] in self._record_ids:
                raise RawLogV2StoreError("duplicate record_id")
            if record["sequence"] <= self._last_sequence:
                raise RawLogV2StoreError("record sequence must increase strictly")

            encoded = json.dumps(
                dict(record), ensure_ascii=False, allow_nan=False, separators=(",", ":")
            )
            records_path = self._package_dir / "records.jsonl"
            with records_path.open("a", encoding="utf-8", newline="") as stream:
                stream.write(encoded + "\n")
                stream.flush()
                os.fsync(stream.fileno())

            self._record_ids.add(record["record_id"])
            self._last_sequence = record["sequence"]
            self._manifest["record_count"] += 1
            counts = self._manifest["record_type_counts"]
            counts[record["record_type"]] = counts.get(record["record_type"], 0) + 1
            self._write_manifest()

    def finalize(self, status: str, ended_at: str, reason: str | None = None) -> Path:
        """Close the active package without changing or deleting its records."""
        with self._lock:
            if not self.active:
                raise RawLogV2StoreError("no active RawLog v2 package")
            if status not in _FINAL_STATUSES:
                raise RawLogV2StoreError("invalid final status")
            if not isinstance(ended_at, str) or not ended_at.strip():
                raise RawLogV2StoreError("ended_at must be non-empty")
            self._manifest["status"] = status
            self._manifest["ended_at"] = ended_at
            self._manifest["final_reason"] = reason
            self._write_manifest()
            result = self._package_dir
            self._manifest = None
            self._package_dir = None
            self._record_ids.clear()
            self._last_sequence = -1
            return result

    def read_records(self, log_id: str) -> list[dict]:
        """Read and revalidate a completed or active package."""
        if not isinstance(log_id, str) or not _LOG_ID_RE.fullmatch(log_id):
            raise RawLogV2StoreError("invalid log_id")
        package_dir = self.root / log_id
        records_path = package_dir / "records.jsonl"
        result = []
        with records_path.open("r", encoding="utf-8") as stream:
            previous_sequence = -1
            for line_number, line in enumerate(stream, start=1):
                if not line.strip():
                    raise RawLogV2StoreError(f"blank record line {line_number}")
                try:
                    record = json.loads(line)
                    validate_record(record)
                except (json.JSONDecodeError, RawLogV2ValidationError) as exc:
                    raise RawLogV2StoreError(f"invalid record line {line_number}: {exc}") from exc
                if record["log_id"] != log_id:
                    raise RawLogV2StoreError(f"log_id mismatch on line {line_number}")
                if record["sequence"] <= previous_sequence:
                    raise RawLogV2StoreError(f"non-increasing sequence on line {line_number}")
                previous_sequence = record["sequence"]
                result.append(record)
        return result

    def _write_manifest(self) -> None:
        manifest_path = self._package_dir / "manifest.json"
        temporary_path = self._package_dir / ".manifest.json.tmp"
        encoded = json.dumps(
            self._manifest, ensure_ascii=False, allow_nan=False, indent=2
        ) + "\n"
        with temporary_path.open("w", encoding="utf-8", newline="") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, manifest_path)
