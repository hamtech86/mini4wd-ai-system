"""Shared local-first diagnostic report bundling and GitHub upload.

RawLog bodies are copied verbatim; this module never edits RawLogLibrary data.
"""
from __future__ import annotations

import base64
import hashlib
import json
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from raw_log_library import RawLogLibrary

DEFAULT_REPOSITORY = "hamtech86/mini4wd-raw-logs"
DEFAULT_API = "https://api.github.com"


class DiagnosticReportError(RuntimeError):
    def __init__(self, message: str, local_bundle: Path | None = None):
        super().__init__(message)
        self.local_bundle = local_bundle


class DiagnosticReportService:
    def __init__(
        self,
        library: RawLogLibrary,
        report_root: str | Path = "data/diagnostic_reports",
        repository: str = DEFAULT_REPOSITORY,
        token: str | None = None,
        api_base: str = DEFAULT_API,
    ) -> None:
        self.library = library
        self.report_root = Path(report_root)
        self.repository = repository
        self.token = token
        self.api_base = api_base.rstrip("/")

    def create_local_bundle(
        self,
        device_type: str,
        log_ids: list[str],
        *,
        ui_events: str = "",
        error_code: str | None = None,
        error_message: str | None = None,
        context: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> Path:
        kind = str(device_type).upper()
        if kind not in {"BATTERY", "MOTOR"}:
            raise ValueError("device_type must be BATTERY or MOTOR")
        selected = list(dict.fromkeys(str(value) for value in log_ids if str(value).strip()))
        if not selected:
            raise ValueError("at least one RawLog must be explicitly selected")
        records = []
        for log_id in selected:
            record, _, _ = self.library.get(log_id)
            if record.device_type.upper() != kind:
                raise ValueError(f"{log_id} is not a {kind} RawLog")
            raw_body = self.library.read_raw(log_id)
            records.append((record, raw_body))

        report_id = run_id or uuid.uuid4().hex
        if not report_id or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for char in report_id):
            raise ValueError("run_id contains unsupported characters")
        bundle = self.report_root / kind.lower() / report_id
        bundle.mkdir(parents=True, exist_ok=False)
        raw_dir = bundle / "raw_logs"
        raw_dir.mkdir()
        entries = []
        for record, raw_body in records:
            filename = f"{record.log_id}.log"
            # Write bytes so CRLF/LF are not translated by platform newline handling.
            (raw_dir / filename).write_bytes(raw_body.encode("utf-8"))
            metadata = {
                "log_id": record.log_id,
                "device_type": record.device_type,
                "device_model": record.device_model,
                "firmware_version": record.firmware_version,
                "device_instance_id": record.device_instance_id,
                "channel": record.channel,
                "motor_id": record.motor_id,
                "battery_id": record.battery_id,
                "measurement_session_id": record.measurement_session_id,
                "acquired_at": record.acquired_at,
                "measurement_condition": record.measurement_condition,
                "source_reference": record.source_reference,
                "notes": record.notes,
                "bundle_path": f"raw_logs/{filename}",
            }
            entries.append(metadata)

        manifest = {
            "schema": "mini4wd-diagnostic-report-v1",
            "run_id": report_id,
            "device_type": kind,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "error": {"code": error_code, "message": error_message},
            "context": context or {},
            "ui_events": ui_events,
            "selected_raw_logs": entries,
            "raw_log_body_policy": "verbatim UTF-8 copy; source RawLogLibrary records are not modified",
        }
        (bundle / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return bundle

    def upload_bundle(self, bundle: str | Path) -> dict[str, Any]:
        bundle = Path(bundle)
        if not bundle.is_dir() or not (bundle / "manifest.json").is_file():
            raise DiagnosticReportError("local diagnostic bundle is missing or incomplete", bundle)
        if not self.token:
            raise DiagnosticReportError("GitHub token is not configured; local bundle was retained", bundle)
        manifest = json.loads((bundle / "manifest.json").read_text(encoding="utf-8"))
        kind = str(manifest.get("device_type", "")).lower()
        run_id = str(manifest.get("run_id", ""))
        if kind not in {"battery", "motor"} or not run_id:
            raise DiagnosticReportError("manifest device_type/run_id is invalid", bundle)
        prefix = f"diagnostic-reports/{kind}/{run_id}"
        files = sorted(
            path for path in bundle.rglob("*")
            if path.is_file() and path.name != "upload_status.json"
        )
        uploaded = []
        try:
            for path in files:
                relative = path.relative_to(bundle).as_posix()
                target = f"{prefix}/{relative}"
                self._put_new_file(target, path.read_bytes(), f"Diagnostic report {run_id}: {relative}")
                uploaded.append(target)
        except Exception as exc:
            raise DiagnosticReportError(
                f"GitHub upload incomplete ({len(uploaded)}/{len(files)} files): {exc}; local bundle retained at {bundle}",
                bundle,
            ) from exc
        result = {
            "status": "UPLOADED",
            "repository": self.repository,
            "run_id": run_id,
            "files": uploaded,
            "local_bundle": str(bundle),
        }
        (bundle / "upload_status.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return result

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2026-03-10",
            "Content-Type": "application/json",
            "User-Agent": "mini4wd-ai-system-diagnostic-report",
        }

    def _put_new_file(self, path: str, content: bytes, message: str) -> dict[str, Any]:
        url = f"{self.api_base}/repos/{self.repository}/contents/{path}"
        lookup = urllib.request.Request(url, method="GET", headers=self._headers())
        try:
            with urllib.request.urlopen(lookup, timeout=15) as response:
                existing = json.loads(response.read().decode("utf-8"))
                existing_sha = existing.get("sha")
                if existing_sha:
                    expected_sha = hashlib.sha1(
                        b"blob " + str(len(content)).encode("ascii") + b"\\0" + content
                    ).hexdigest()
                    if existing_sha == expected_sha:
                        # Safe retry after a partial upload: identical content is already present.
                        return {"status": "ALREADY_PRESENT_IDENTICAL", "path": path, "sha": existing_sha}
                    raise DiagnosticReportError(f"duplicate upload blocked; different content already exists: {path}")
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                detail = exc.read().decode("utf-8", errors="replace")
                raise DiagnosticReportError(f"GitHub lookup error {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise DiagnosticReportError(f"GitHub lookup network error: {exc.reason}") from exc

        payload = {
            "message": message,
            "content": base64.b64encode(content).decode("ascii"),
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            method="PUT",
            headers=self._headers(),
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise DiagnosticReportError(f"GitHub upload error {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise DiagnosticReportError(f"GitHub upload network error: {exc.reason}") from exc
