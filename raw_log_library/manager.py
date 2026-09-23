"""Common manager for immutable Motor/Battery raw logs.

Raw bodies are immutable. Editable metadata, including the user-selected
History flag, is kept separately from the raw body.
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
    "history_registered",
]


@dataclass
class RawLog:
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
    history_registered: str = "0"


class RawLogLibrary:
    """Filesystem-backed raw-log library with an immutable raw-body boundary."""

    ID_WIDTH = 6
    _ID_PATTERN = re.compile(r"^(MOTOR|BATTERY)-(\d{6})(?:_|$)")

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
        kind = device_type.upper()
        if kind not in {"MOTOR", "BATTERY"}:
            raise ValueError("device_type must be MOTOR or BATTERY")
        prefix = f"{kind}-"
        maximum = 0
        for row in self._read_index():
            match = self._ID_PATTERN.fullmatch(str(row.get("log_id") or ""))
            if match and match.group(1) == kind:
                maximum = max(maximum, int(match.group(2)))
        for search_root in (self.root / kind.lower(), self.root.parent):
            if not search_root.exists():
                continue
            try:
                paths = search_root.rglob(f"{prefix}*")
            except OSError:
                continue
            for path in paths:
                match = self._ID_PATTERN.match(path.stem)
                if match and match.group(1) == kind:
                    maximum = max(maximum, int(match.group(2)))
        return f"{prefix}{maximum + 1:0{self.ID_WIDTH}d}"

    def register(self, record: RawLog, raw_body: str, extension: str = ".log") -> Path:
        if record.log_id:
            raise ValueError("new Raw Log log_id must not be supplied; Library allocates it")
        if not extension.startswith("."):
            extension = "." + extension
        record.log_id = self._next_log_id(record.device_type)
        record.history_registered = "0"
        device_dir = self._device_dir(record)
        device_dir.mkdir(parents=True, exist_ok=True)
        raw_path = device_dir / f"{record.log_id}{extension}"
        metadata_path = self._metadata_path(record)
        if raw_path.exists():
            raise FileExistsError(f"allocated raw log already exists: {raw_path}")
        metadata = {}
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if not isinstance(metadata, dict):
                raise ValueError(f"invalid metadata store: {metadata_path}")
            if record.log_id in metadata:
                raise FileExistsError(f"metadata already exists for log_id: {record.log_id}")
        raw_path.write_text(raw_body, encoding="utf-8", newline="")
        metadata[record.log_id] = asdict(record)
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self._append_index(self._index_row(record, raw_path))
        return raw_path

    def update_metadata(self, log_id: str, **changes: str) -> RawLog:
        if "log_id" in changes:
            raise ValueError("log_id is immutable")
        record, raw_path, metadata_path = self.get(log_id)
        allowed = set(INDEX_FIELDS) - {"log_id", "raw_path", "metadata_path"}
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(f"unsupported metadata fields: {sorted(unknown)}")
        data = asdict(record)
        data.update(changes)
        updated = RawLog(**{key: data.get(key) for key in asdict(RawLog())})
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        metadata[log_id] = asdict(updated)
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self._rewrite_index_row(updated, raw_path)
        return updated

    def set_history_registered(self, log_id: str, registered: bool) -> RawLog:
        return self.update_metadata(log_id, history_registered="1" if registered else "0")

    def is_history_registered(self, log_id: str) -> bool:
        return self.get(log_id)[0].history_registered == "1"

    def get(self, log_id: str) -> tuple[RawLog, Path, Path]:
        for row in self._read_index():
            if row.get("log_id") != log_id:
                continue
            metadata_path = self.root / row["metadata_path"]
            raw_path = self.root / row["raw_path"]
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            data = dict(metadata[log_id])
            data.setdefault("history_registered", row.get("history_registered", "0") or "0")
            allowed = set(asdict(RawLog()))
            data = {k:v for k,v in data.items() if k in allowed}
            return RawLog(**data), raw_path, metadata_path
        raise KeyError(f"unknown log_id: {log_id}")

    def read_raw(self, log_id: str) -> str:
        return self.get(log_id)[1].read_text(encoding="utf-8")

    def list_logs(self, device_type: Optional[str] = None) -> List[RawLog]:
        result = []
        for row in self._read_index():
            if device_type and row.get("device_type","").upper() != device_type.upper():
                continue
            result.append(self.get(row["log_id"])[0])
        return result

    def list_by_session(self, measurement_session_id: str) -> List[RawLog]:
        return [r for r in self.list_logs() if r.measurement_session_id == str(measurement_session_id)]

    @property
    def github_status_path(self) -> Path:
        return self.root / "github_status.json"

    def get_github_status(self, log_id: str) -> Dict[str, str]:
        self.get(log_id)
        if not self.github_status_path.exists():
            return {"status": "UNREGISTERED"}
        data = json.loads(self.github_status_path.read_text(encoding="utf-8"))
        value = data.get(log_id, {"status": "UNREGISTERED"})
        return value if isinstance(value, dict) else {"status": "UNREGISTERED"}

    def set_github_status(self, log_id: str, status: str, **details: str) -> None:
        self.get(log_id)
        data = {}
        if self.github_status_path.exists():
            loaded = json.loads(self.github_status_path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError(f"invalid GitHub status store: {self.github_status_path}")
            data = loaded
        value = {"status": status}
        value.update({key:str(val) for key,val in details.items() if val is not None})
        self.github_status_path.parent.mkdir(parents=True, exist_ok=True)
        self.github_status_path.write_text(json.dumps({**data, log_id:value}, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")

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
        for i,row in enumerate(rows):
            if row.get("log_id") == record.log_id:
                rows[i] = replacement
                break
        else:
            raise KeyError(f"unknown log_id: {record.log_id}")
        with self.index_path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=INDEX_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
