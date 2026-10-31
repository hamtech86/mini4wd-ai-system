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
        # Search only this library's storage tree. Searching self.root.parent
        # mixes unrelated libraries/test fixtures and causes IDs to skip.
        if self.root.exists():
            try:
                paths = self.root.rglob(f"{prefix}*")
                for path in paths:
                    match = self._ID_PATTERN.match(path.stem)
                    if match and match.group(1) == kind:
                        maximum = max(maximum, int(match.group(2)))
            except OSError:
                pass
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

    def register_v2_aux(self, log_id: str, records, parse_errors=None) -> Optional[Dict[str, str]]:
        """Persist AUX v2 beside an existing immutable RawLog body.

        Legacy DATA bodies and index/metadata schemas are deliberately untouched.
        A v2 manifest is created only when this log actually has AUX content.
        """
        import os
        from dataclasses import is_dataclass

        _, raw_path, _ = self.get(log_id)
        parse_errors = list(parse_errors or [])
        normalized = []
        for record in records or []:
            value = asdict(record) if is_dataclass(record) else dict(record)
            normalized.append(value)
        if not normalized and not parse_errors:
            return None

        aux_path = raw_path.with_suffix(".aux.jsonl")
        manifest_path = raw_path.with_suffix(".manifest.json")
        if aux_path.exists() or manifest_path.exists():
            raise FileExistsError(f"RawLog v2 sidecar already exists for {log_id}")

        def atomic_write(path: Path, content: str) -> None:
            temporary = path.with_name(path.name + ".tmp")
            try:
                temporary.write_text(content, encoding="utf-8", newline="")
                os.replace(temporary, path)
            finally:
                if temporary.exists():
                    temporary.unlink()

        aux_lines = []
        for value in normalized:
            aux_lines.append(json.dumps({
                "record_type": "AUX",
                "protocol_version": value.get("protocol_version"),
                "session_id": value.get("session_id"),
                "sequence": value.get("sequence"),
                "phase": value.get("phase"),
                "direction": value.get("direction"),
                "pwm": value.get("pwm"),
                "run_state": value.get("run_state"),
                "channel": value.get("channel"),
                "adc_raw": value.get("adc_raw"),
                "timestamp_us": value.get("timestamp_us"),
                "raw_line": value.get("raw_line"),
            }, ensure_ascii=False, separators=(",", ":")))
        if normalized:
            atomic_write(aux_path, "".join(line + "\n" for line in aux_lines))

        manifest = {
            "schema": "mini4wd.rawlog.v2",
            "log_id": log_id,
            "raw_body": raw_path.name,
            "raw_body_format": "legacy_serial_text_immutable",
            "aux_records": aux_path.name if normalized else None,
            "aux_record_count": len(normalized),
            "aux_parse_errors": parse_errors,
            "derived_records": None,
            "derived_status": "NOT_GENERATED",
        }
        atomic_write(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
        return {
            "manifest_path": str(manifest_path),
            "aux_path": str(aux_path) if normalized else "",
        }

    def register_v2_derived(self, log_id: str, records) -> Optional[str]:
        """Persist reproducible derived outputs without performing analysis."""
        import math
        import os

        _, raw_path, _ = self.get(log_id)
        normalized = []
        required = {
            "metric", "algorithm_id", "algorithm_version",
            "input_sample_ids", "value", "unit", "valid", "invalid_reason",
        }
        for item in records or []:
            value = dict(item)
            missing = required - set(value)
            if missing:
                raise ValueError(f"derived record missing fields: {sorted(missing)}")
            if not isinstance(value["metric"], str) or not value["metric"].strip():
                raise ValueError("derived metric must be a non-empty string")
            if not isinstance(value["algorithm_id"], str) or not value["algorithm_id"].strip():
                raise ValueError("derived algorithm_id must be a non-empty string")
            if not isinstance(value["algorithm_version"], str) or not value["algorithm_version"].strip():
                raise ValueError("derived algorithm_version must be a non-empty string")
            ids = value["input_sample_ids"]
            if not isinstance(ids, list) or not ids or any(not isinstance(x, str) or not x for x in ids):
                raise ValueError("input_sample_ids must be a non-empty list of sample IDs")
            if type(value["valid"]) is not bool:
                raise ValueError("derived valid must be boolean")
            if value["valid"]:
                if value["value"] is None or value["invalid_reason"] not in (None, ""):
                    raise ValueError("valid derived records require a value and no invalid_reason")
                if isinstance(value["value"], bool) or not isinstance(value["value"], (int, float)):
                    raise ValueError("valid derived value must be numeric")
                if not math.isfinite(float(value["value"])):
                    raise ValueError("valid derived value must be finite")
            elif not isinstance(value["invalid_reason"], str) or not value["invalid_reason"].strip():
                raise ValueError("invalid derived records require an invalid_reason")
            normalized.append({
                "record_type": "DERIVED",
                **{key: value[key] for key in sorted(required)},
            })
        if not normalized:
            return None

        manifest_path = raw_path.with_suffix(".manifest.json")
        derived_path = raw_path.with_suffix(".derived.jsonl")
        if derived_path.exists():
            raise FileExistsError(f"Derived sidecar already exists for {log_id}")
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if manifest.get("schema") != "mini4wd.rawlog.v2" or manifest.get("log_id") != log_id:
                raise ValueError(f"invalid RawLog v2 manifest: {manifest_path}")
        else:
            manifest = {
                "schema": "mini4wd.rawlog.v2",
                "log_id": log_id,
                "raw_body": raw_path.name,
                "raw_body_format": "legacy_serial_text_immutable",
                "aux_records": None,
                "aux_record_count": 0,
                "aux_parse_errors": [],
            }

        def atomic_write(path: Path, content: str) -> None:
            temporary = path.with_name(path.name + ".tmp")
            try:
                temporary.write_text(content, encoding="utf-8", newline="")
                os.replace(temporary, path)
            finally:
                if temporary.exists():
                    temporary.unlink()

        payload = "".join(
            json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\\n"
            for item in normalized
        )
        atomic_write(derived_path, payload)
        manifest["derived_records"] = derived_path.name
        manifest["derived_record_count"] = len(normalized)
        manifest["derived_status"] = "AVAILABLE"
        atomic_write(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\\n")
        return str(derived_path)

    def read_v2_derived(self, log_id: str) -> List[Dict[str, object]]:
        manifest = self.read_v2_manifest(log_id)
        if manifest is None or not manifest.get("derived_records"):
            return []
        _, raw_path, _ = self.get(log_id)
        derived_path = raw_path.parent / str(manifest["derived_records"])
        with derived_path.open("r", encoding="utf-8", newline="") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def read_v2_manifest(self, log_id: str) -> Optional[Dict[str, object]]:
        """Read an explicitly registered v2 manifest; v1 logs return None."""
        _, raw_path, _ = self.get(log_id)
        manifest_path = raw_path.with_suffix(".manifest.json")
        if not manifest_path.exists():
            return None
        value = json.loads(manifest_path.read_text(encoding="utf-8"))
        if value.get("schema") != "mini4wd.rawlog.v2" or value.get("log_id") != log_id:
            raise ValueError(f"invalid RawLog v2 manifest: {manifest_path}")
        return value

    def read_v2_aux(self, log_id: str) -> List[Dict[str, object]]:
        manifest = self.read_v2_manifest(log_id)
        if manifest is None or not manifest.get("aux_records"):
            return []
        _, raw_path, _ = self.get(log_id)
        aux_path = raw_path.parent / str(manifest["aux_records"])
        with aux_path.open("r", encoding="utf-8", newline="") as fh:
            return [json.loads(line) for line in fh if line.strip()]

    def update_metadata(self, *args: str, **changes: str) -> RawLog:
        # Keep log_id positional-only so attempts to mutate it via keyword
        # reach the immutability check instead of Python's duplicate-arg error.
        if len(args) != 1:
            raise TypeError("update_metadata() requires one positional log_id")
        log_id = args[0]
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
        # Preserve CRLF and LF exactly; read_text() translates newlines.
        with self.get(log_id)[1].open("r", encoding="utf-8", newline="") as fh:
            return fh.read()

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
