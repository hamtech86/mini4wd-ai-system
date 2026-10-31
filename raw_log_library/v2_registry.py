"""Independent RawLog v2 local registry and ID allocator.

The registry is the local management index for v2 packages. It deliberately
never reads or writes v1 files, databases, or indexes. Package records remain
append-only; only the explicitly mutable management fields are stored here.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import time
from contextlib import contextmanager
from typing import Mapping


_ID_RE = re.compile(r"^MOTOR-(\d{6})$")
_MUTABLE_FIELDS = {
    "motor_instance_id",
    "instance_visible",
    "note",
    "history_registered",
    "github_status",
    "github_repository",
    "github_path",
    "github_registered_at",
}


class RawLogV2RegistryError(ValueError):
    """Raised when v2 registry data cannot be safely managed."""


class RawLogV2Registry:
    """Manages v2 package discovery, immutable IDs, and editable associations."""

    def __init__(self, root: str | Path = "data/raw_logs_v2") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.index_path = self.root / "registry.json"
        self.lock_path = self.root / ".registry.lock"

    @contextmanager
    def _locked(self):
        deadline = time.monotonic() + 10.0
        while True:
            try:
                self.lock_path.mkdir()
                break
            except FileExistsError:
                if time.monotonic() >= deadline:
                    raise RawLogV2RegistryError("timed out waiting for v2 registry lock")
                time.sleep(0.025)
        try:
            yield
        finally:
            try:
                self.lock_path.rmdir()
            except OSError:
                pass

    def _read_index(self) -> dict:
        if not self.index_path.exists():
            return {"schema": "mini4wd.rawlog.v2.registry", "entries": {}}
        try:
            data = json.loads(self.index_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RawLogV2RegistryError(f"cannot read v2 registry: {exc}") from exc
        if data.get("schema") != "mini4wd.rawlog.v2.registry" or not isinstance(data.get("entries"), dict):
            raise RawLogV2RegistryError("invalid v2 registry structure")
        return data

    def _write_index(self, data: dict) -> None:
        temporary = self.index_path.with_suffix(".json.tmp")
        encoded = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        with temporary.open("w", encoding="utf-8", newline="") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, self.index_path)

    def _used_ids(self, entries: Mapping) -> set[str]:
        used = set(entries)
        for child in self.root.iterdir():
            if child.is_dir() and _ID_RE.fullmatch(child.name):
                used.add(child.name)
        return used

    def create_package(self, store, manifest: Mapping, *, motor_instance_id: str) -> Path:
        """Allocate an ID exactly once and create its v2 package under one lock."""
        if not isinstance(motor_instance_id, str) or not motor_instance_id.strip():
            raise RawLogV2RegistryError("motor_instance_id must be selected before measurement")
        with self._locked():
            index = self._read_index()
            used = self._used_ids(index["entries"])
            next_number = 1
            while f"MOTOR-{next_number:06d}" in used:
                next_number += 1
            if next_number > 999999:
                raise RawLogV2RegistryError("MOTOR RawLog ID space exhausted")
            log_id = f"MOTOR-{next_number:06d}"
            package_manifest = dict(manifest)
            if "log_id" in package_manifest and package_manifest["log_id"] != log_id:
                raise RawLogV2RegistryError("caller must not supply or override log_id")
            package_manifest["log_id"] = log_id
            package_manifest["motor_instance_id"] = motor_instance_id
            package_dir = store.create(package_manifest)
            index["entries"][log_id] = {
                "log_id": log_id,
                "motor_instance_id": motor_instance_id,
                "instance_visible": True,
                "note": "",
                "history_registered": False,
                "github_status": "UNREGISTERED",
                "github_repository": None,
                "github_path": None,
                "github_registered_at": None,
            }
            try:
                self._write_index(index)
            except Exception:
                # Do not delete or reuse an already-created package/ID. It is
                # recoverable by discover_packages() and remains immutable.
                raise
            return package_dir

    def discover_packages(self) -> list[dict]:
        """Return every package, including packages absent from the registry."""
        index = self._read_index()
        result = []
        for package_dir in sorted(self.root.glob("MOTOR-*")):
            manifest_path = package_dir / "manifest.json"
            records_path = package_dir / "records.jsonl"
            if not package_dir.is_dir() or not manifest_path.is_file() or not records_path.is_file():
                continue
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                result.append({"log_id": package_dir.name, "integrity": "ERROR", "error": str(exc)})
                continue
            entry = dict(index["entries"].get(package_dir.name, {}))
            result.append({
                **manifest,
                **entry,
                "log_id": package_dir.name,
                "integrity": "OK",
                "package_path": str(package_dir),
            })
        return sorted(result, key=lambda item: (str(item.get("started_at") or ""), item["log_id"]))

    def update_management(self, log_id: str, **changes) -> dict:
        """Edit only association/presentation/note/history/GitHub metadata."""
        unknown = set(changes) - _MUTABLE_FIELDS
        if unknown:
            raise RawLogV2RegistryError("immutable or unsupported fields: " + ", ".join(sorted(unknown)))
        with self._locked():
            index = self._read_index()
            if log_id not in index["entries"]:
                raise RawLogV2RegistryError(f"unknown v2 log_id: {log_id}")
            entry = index["entries"][log_id]
            for key, value in changes.items():
                if key == "motor_instance_id" and value is not None and (
                    not isinstance(value, str) or not value.strip()
                ):
                    raise RawLogV2RegistryError("motor_instance_id must be a non-empty string or null")
                if key == "note" and not isinstance(value, str):
                    raise RawLogV2RegistryError("note must be a string")
                if key in {"instance_visible", "history_registered"} and type(value) is not bool:
                    raise RawLogV2RegistryError(f"{key} must be boolean")
                if key == "github_status" and value not in {"UNREGISTERED", "REGISTERED", "ERROR"}:
                    raise RawLogV2RegistryError("invalid github_status")
                entry[key] = value
            self._write_index(index)
            return dict(entry)

    def get(self, log_id: str) -> dict:
        for item in self.discover_packages():
            if item.get("log_id") == log_id:
                return item
        raise RawLogV2RegistryError(f"unknown v2 log_id: {log_id}")
