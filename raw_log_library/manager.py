"""Common manager for immutable Motor/Battery raw logs.

The manager treats ``log_id`` as the logical entry point. Raw bodies are
stored separately from editable management metadata, so metadata updates do
not modify the original log body.
"""

from __future__ import annotations

import csv
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional


INDEX_FIELDS = [
    "log_id", "device_type", "device_model", "firmware_version",
    "device_instance_id", "channel", "motor_id", "battery_id",
    "measurement_session_id", "acquired_at", "measurement_condition",
    "source_reference", "raw_path", "metadata_path", "notes",
]


@dataclass
class RawLog:
    # log_id is allocated by RawLogLibrary.register(); callers may leave it
    # empty for new records. Existing records retain their original ID.
    log_id: str = ""
    device_type: str = "MOTOR"
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

    ID_WIDTH = 6
    _ID_PATTERN = re.compile(r"^(MOTOR|BATTERY)-(\d{6})$")

    def __init__(self, root: str | Path = "data/raw_logs") -> None:
        self.root = Path(root)
        self.index_path = self.root / "index.csv"

    def _device_dir(self, record: RawLog) -> Path:
        kind = record.device_type.upper()
        if kind not in {"MOTOR", "BATTERY"}:
            raise ValueError("device_type must be MOTOR or BATTERY")
        individual_id = record.motor_id if kind == "MOTOR" else record.battery_id
        return self.root / kind.lower() / (individual_id or "UNASSIGNED")

    def _metadata_path(self, record: RawLog) -> Path:
        return self._device_dir(record) / "metadata.json"

    def _index_row(self, record: RawLog, raw_path: Path) -> Dict[str, str]:
        row = asdict(record)
        row["raw_path"] = str(raw_path.relative_to(self.root))
        row["metadata_path"] = str(self._metadata_path(record).relative_to(self.root))
        return {field: "" if row.get(field) is None else str(row.get(field)) for field in INDEX_FIELDS}

    def _next_log_id(self, device_type: str) -> str:
        """Allocate the next per-device-type ID without consulting callers."""
        kind = device_type.upper()
        if kind not in {"MOTOR", "BATTERY"}:
            raise ValueError("device_type must be MOTOR or BATTERY")

        prefix = f"{kind}-"
        maximum = 0
        for row in self._read_index():
            log_id = str(row.get("log_id") or "")
            match = self._ID_PATTERN.fullmatch(log_id)
            if match and match.group(1) == kind:
                maximum = max(maximum, int(match.group(2)))

        # Compatibility guard: historical logs may exist outside the current
        # index. Their IDs are never rewritten, but their numbers must not be
        # reissued. Scan the Local library and the surrounding data tree for
        # canonical legacy IDs (for example data/motor_logs/MOTOR-000001_*).
        for search_root in (self.root / kind.lower(), self.root.parent):
            if not search_root.exists():
                continue
            try:
                paths = search_root.rglob(f"{prefix}*")
            except OSError:
                continue
            for path in paths:
                match = self._ID_PATTERN.fullmatch(path.stem)
                if match and match.group(1) == kind:
                    maximum = max(maximum, int(match.group(2)))

        return f"{prefix}{maximum + 1:0{self.ID_WIDTH}d}"

    def register(self, record: RawLog, raw_body: str, extension: str = ".log") -> Path:
        """Register a new raw log and allocate its immutable logical ID."""
        if record.log_id:
            raise ValueError("new Raw Log log_id must not be supplied; Library allocates it")
        if not extension.startswith("."):
            extension = "." + extension

        record.log_id = self._next_log_id(record.device_type)
        device_dir = self._device_dir(record)
        device_dir.mkdir(parents=True, exist_ok=True)
        raw_path = device_dir / f"{record.log_id}{extension}"
        metadata_path = self._metadata_path(record)
        if raw_path.exists():
            raise FileExistsError(f"allocated raw log already exists: {raw_path}")

        # One metadata.json is maintained per individual, keyed by log_id.
        metadata = {}
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if not isinstance(metadata, dict):
                raise ValueError(f"invalid metadata store: {metadata_path}")
            if record.log_id in metadata:
                raise FileExistsError(f"metadata already exists for log_id: {record.log_id}")

        # Raw body is written exactly as supplied. No parsing or derived values.
        raw_path.write_text(raw_body, encoding="utf-8", newline="")
        metadata[record.log_id] = asdict(record)
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        self._append_index(self._index_row(record, raw_path))
        return raw_path

    def update_metadata(self, log_id: str, **changes: str) -> RawLog:
        """Update management tags only; never touches the raw body or log_id."""
        if "log_id" in changes:
            raise ValueError("log_id is immutable")
        record, raw_path, metadata_path = self.get(log_id)
        allowed = set(INDEX_FIELDS) - {"log_id", "raw_path", "metadata_path"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"unsupported metadata fields: {sorted(unknown)}")

        data = asdict(record)
        data.update(changes)
        updated = RawLog(**{key: data.get(key) for key in asdict(record)})
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata[log_id] = asdict(updated)
        metadata_path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        self._rewrite_index_row(updated, raw_path)
        return updated

    def get(self, log_id: str) -> tuple[RawLog, Path, Path]:
        """Resolve a log by logical ``log_id``, not by storage path."""
        for row in self._read_index():
            if row.get("log_id") != log_id:
                continue
            metadata_path = self.root / row["metadata_path"]
            raw_path = self.root / row["raw_path"]
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            data = metadata[log_id]
            return RawLog(**data), raw_path, metadata_path
        raise KeyError(f"unknown log_id: {log_id}")

    def read_raw(self, log_id: str) -> str:
        """Return the raw body without parsing or modifying it."""
        _, raw_path, _ = self.get(log_id)
        return raw_path.read_text(encoding="utf-8")

    def list_logs(self, device_type: Optional[str] = None) -> List[RawLog]:
        result: List[RawLog] = []
        for row in self._read_index():
            if device_type and row.get("device_type", "").upper() != device_type.upper():
                continue
            result.append(self.get(row["log_id"])[0])
        return result

    def list_by_session(self, measurement_session_id: str) -> List[RawLog]:
        """Return Raw Logs linked to one Measurement Session."""
        return [
            record
            for record in self.list_logs()
            if record.measurement_session_id == measurement_session_id
        ]

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
        replacement = self._index_row(record, raw_path)
        for i, row in enumerate(rows):
            if row.get("log_id") == record.log_id:
                rows[i] = replacement
                break
        else:
            raise KeyError(f"unknown log_id: {record.log_id}")
        with self.index_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=INDEX_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
