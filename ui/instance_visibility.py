"""Local-only Instance Manager visibility state.

Visibility is deliberately kept outside motor_instance.is_deleted. It is UI
management state and must not alter the database records.
"""
from __future__ import annotations

import json
from pathlib import Path


class InstanceVisibilityStore:
    VALUES = {"VISIBLE", "HIDDEN"}

    def __init__(self, root: str | Path = "data/instance_manager"):
        self.path = Path(root) / "visibility.json"

    def _load(self):
        if not self.path.exists():
            return {}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, json.JSONDecodeError):
            return {}

    def get(self, instance_id) -> str:
        return "HIDDEN" if self._load().get(str(instance_id)) == "HIDDEN" else "VISIBLE"

    def set(self, instance_id, value: str) -> None:
        value = str(value).upper()
        if value not in self.VALUES:
            raise ValueError(f"visibility must be VISIBLE or HIDDEN: {value}")
        data = self._load()
        if value == "VISIBLE":
            data.pop(str(instance_id), None)
        else:
            data[str(instance_id)] = "HIDDEN"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def filter_ids(self, ids, mode="VISIBLE"):
        mode = str(mode).upper()
        if mode == "ALL":
            return list(ids)
        return [iid for iid in ids if self.get(iid) == mode]
