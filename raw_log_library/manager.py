"""Common manager for immutable Motor/Battery raw logs.

The manager treats ``log_id`` as the logical entry point.  Raw bytes/text are
stored separately from editable management metadata, so metadata updates do
not modify the original log body.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional


INDEX_FIELDS = [
    "log_id",
    "device_type",
    "device_model",
    "firmware_version",
    "device_instance_id",
    "channel",
    "motor_id",
    "battery_id",
    "measurement_session_id",
    "acquired_at",
    "measurement_condition",
    "source_reference",
    "raw_path",
    "metadata_path",
    "notes",
]


@dataclass
class RawLog:
    log_id: str
    device_type: str
    device_model: str = ""
    firmware_version: str = ""
    device_instance_id: Optional[str] = None
    channel: Optional[str] = None
    motor_id: Optional[str] = None
    battery_id: Optional[str] = None
    measurement_session_id: Optional[str] = None
    acquired_at: Optional[str] = None
    measurement_condition: str = ""
    source_reference: str = ""
    notes: str = ""


class RawLogLibrary:
    """Filesystem-backed raw-log library with an immutable raw-body boundary."""

    def __init__(self, root: str | Path = "data/raw_logs") -> None:
        self.root = Path(root)
        self.index_path = self.root / "index.csv"

    def _device_dir(self, record: RawLog) -> Path:
        if record.device_type.upper() not in {"MOTOR", "BATTERY"}:
            raise ValueError("device_type must be MOTOR or BATTERY")
        individual_id = record.motor_id if record.device_type.upper() == "MOTOR" else record.battery_id
        individual_id = individual_id or "UNASSIGNED"
        return self.root / record.device_type.lower() / individual_id

    def _metadata_path(self, record: RawLog) -> Path:
        return self._device_dir(record) / "metadata.json"

    def _index_row(self, record: RawLog, raw_path: Path) -> Dict[str, str]:
        row = asdict(record)
        row["raw_path"] = str(raw_path.relative_to(self.root))
        row["metadata_path"] = str(self._metadata_path(record).relative_to(self.root))
        return {field: "" if row.get(field) is None else str(row.get(field)) for field in INDEX_FIELDS}

    def register(self, record: RawLog, raw_body: str, extension: str = ".log") -> Path:
        """Register a new raw log; refuse to overwrite an existing raw body."""
        if not record.log_id:
            raise ValueError("log_id is required")
        if not extension.startswith("."):
            extension = "." + extension

        device_dir = self._device_dir(record)
        device_dir.mkdir(parents=True, exist_ok=True)
        raw_path = device_dir / f"{record.log_id}{extension}"
        metadata_path = self._metadata_path(record)

        if raw_path.exists():
            raise FileExistsError(f"immutable raw log already exists: {raw_path}")
        if metadata_path.exists():
            raise FileExistsError(f"metadata already exists for individual: {metadata_path}")

        # Write raw body exactly as supplied. No parsing, normalization, or derived values.
        raw_path.write_text(raw_body, encoding="utf-8", newline="")
        metadata_path.write_text(
            json.dumps(asdict(record), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self._append_index(self._index_row(record, raw_path))
        return raw_path

    def update_metadata(self, log_id: str, **changes: str) -> RawLog:
        """Update management tags only; never touches the raw body."""
        record, raw_path, metadata_path = self.get(log_id)
        allowed = set(INDEX_FIELDS) - {"raw_path", "metadata_path"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"unsupported metadata fields: {sorted(unknown)}")

        data = asdict(record)
        data.update(changes)
        updated = RawLog(**{key: data.get(key) for key in asdict(record)})
        metadata_path.write_text(
            json.dumps(asdict(updated), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self._rewrite_index_row(updated, raw_path)
        return updated

    def get(self, log_id: str) -> tuple[RawLog, Path, Path]:
        """Resolve a log by logical ``log_id`` rather than by storage path."""
        rows = self._read_index()
        for row in rows:
            if row.get("log_id") == log_id:
                metadata_path = self.root / row["metadata_path"]
                raw_path = self.root / row["raw_path"]
                data = json.loads(metadata_path.read_text(encoding="utf-8"))
                return RawLog(**data), raw_path, metadata_path
        raise KeyError(f"unknown log_id: {log_id}")

    def read_raw(self, log_id: str) -> str:
        """Return the raw body without parsing or modifying it."""
        _, raw_path, _ = self.get(log_id)
        return raw_path.read_text(encoding="utf-8")

    def list_logs(self, device_type: Optional[str] = None) -> List[RawLog]:
        rows = self._read_index()
        result: List[RawLog] = []
        for row in rows:
            if device_type and row.get("device_type", "").upper() != device_type.upper():
                continue
            _, _, metadata_path = self.get(row["log_id"])
            result.append(RawLog(**json.loads(metadata_path.read_text(encoding="utf-8"))))
        return result

    def _read_index(self) -> List[Dict[str, str]]:
        if not self.index_path.exists():
            return []
        with self.index_path.open("r", encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))

    def _append_index(self, row: Dict[str, str]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        exists = self.index_path.exists()
        with self.index_path.open("a", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=INDEX_FIELDS)
            if not exists:
                writer.writeheader()
            writer.writerow(row)

    def _rewrite_index_row(self, record: RawLog, raw_path: Path) -> None:
        rows = self._read_index()
        found = False
        replacement = self._index_row(record, raw_path)
        for i, row in enumerate(rows):
            if row.get("log_id") == record.log_id:
                rows[i] = replacement
                found = True
                break
        if not found:
            raise KeyError(f"unknown log_id: {record.log_id}")
        with self.index_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=INDEX_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
