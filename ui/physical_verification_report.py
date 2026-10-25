"""Prepare and upload a single physical-verification bundle.

The local bundle is written before any network request so an upload failure
never destroys the evidence. Original RawLog bodies are copied verbatim.
"""
from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QCheckBox, QDialog, QDialogButtonBox, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QVBoxLayout,
)

from raw_log_library import RawLogLibrary

REPOSITORY = "hamtech86/mini4wd-raw-logs"
TOKEN_ENV = "MINI4WD_GITHUB_TOKEN"


def _safe(value):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "unknown")).strip("._") or "unknown"


class PhysicalVerificationReport:
    def __init__(self, window):
        self.window = window
        self.root = Path(__file__).resolve().parents[1]
        self.library = RawLogLibrary(self.root / "data" / "raw_logs")

    def send(self):
        instance_id = self.window.instance.currentData() if hasattr(self.window, "instance") else None
        if instance_id is None:
            QMessageBox.warning(self.window, "Verification report", "先に検証対象の MOTOR INSTANCE を選択してください。")
            return

        records = [
            r for r in self.library.list_logs("MOTOR")
            if str(r.device_instance_id or "") == str(instance_id)
        ]
        selected = self._choose_logs(records, instance_id)
        if selected is None:
            return

        now = datetime.now(timezone.utc)
        run_id = f"VERIFY-{now.strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:8].upper()}"
        recipe = ""
        if hasattr(self.window, "recipe"):
            recipe = str(self.window.recipe.currentData() or self.window.recipe.currentText())
        controller = None
        try:
            controller = self.window._motor_controller()
        except Exception:
            pass
        identity = {}
        if controller is not None:
            for key in ("identity_verified", "firmware_version", "device_model", "device_id", "build"):
                value = getattr(controller, key, None)
                if value is not None:
                    identity[key] = value

        history = self.window.ui_log.toPlainText() if hasattr(self.window, "ui_log") else ""
        error_code = getattr(self.window, "_ui_error_code", None)
        error_message = getattr(self.window, "_ui_error_message", None)
        report = {
            "verification_run_id": run_id,
            "created_at_utc": now.isoformat(),
            "repository": REPOSITORY,
            "motor_instance_id": str(instance_id),
            "recipe": recipe,
            "device_identity": identity,
            "error": {"code": error_code, "message": error_message},
            "included_raw_log_ids": [r.log_id for r in selected],
            "notes": "Physical observations must be entered in the UI history before sending; CI/source status is not physical verification.",
        }

        local_dir = self.root / "data" / "verification_reports" / run_id
        raw_dir = local_dir / "raw-logs"
        raw_dir.mkdir(parents=True, exist_ok=False)
        (local_dir / "report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (local_dir / "ui-history.log").write_text(history, encoding="utf-8", newline="")
        (local_dir / "error-details.txt").write_text(
            f"Error Code: {error_code or '--'}\nError Message: {error_message or '--'}\n",
            encoding="utf-8",
        )
        for record in selected:
            body = self.library.read_raw(record.log_id)
            (raw_dir / f"{_safe(record.log_id)}.log").write_text(body, encoding="utf-8", newline="")

        preview = (
            f"Verification run: {run_id}\nInstance: {instance_id}\nRecipe: {recipe or '--'}\n"
            f"RawLogs: {', '.join(r.log_id for r in selected) if selected else '(none selected)'}\n"
            f"Local recovery copy: {local_dir}\n\nGitHubへ送信しますか？"
        )
        if QMessageBox.question(
            self.window, "Send Verification Report — Confirm", preview,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) != QMessageBox.Yes:
            QMessageBox.information(self.window, "Verification report saved", f"送信せずローカル保存しました。\n{local_dir}")
            return

        try:
            self._upload_directory(local_dir, run_id)
        except Exception as exc:
            QMessageBox.critical(
                self.window, "Verification upload failed",
                f"GitHub送信に失敗しました。ローカル保存は残っています。\n{local_dir}\n\n{exc}",
            )
            return
        QMessageBox.information(
            self.window, "Verification report uploaded",
            f"送信しました。\nRun: {run_id}\nRepository: {REPOSITORY}\nLocal copy: {local_dir}",
        )

    def _choose_logs(self, records, instance_id):
        dialog = QDialog(self.window)
        dialog.setWindowTitle("Select RawLogs for this verification")
        dialog.resize(620, 460)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(
            f"Instance {instance_id} に関連付けられたRawLogです。今回の検証に使うログだけ選択してください。"
            "自動で全件添付はしません。"
        ))
        listing = QListWidget()
        for record in sorted(records, key=lambda r: (r.acquired_at or "", r.log_id), reverse=True):
            label = f"{record.log_id} | {record.acquired_at or 'date unknown'} | {record.measurement_condition or 'condition unknown'} | session={record.measurement_session_id or '--'}"
            item = QListWidgetItem(label)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setData(Qt.UserRole, record.log_id)
            listing.addItem(item)
        layout.addWidget(listing)
        layout.addWidget(QLabel("RawLogを選ばずに送ることもできます。"))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec_() != QDialog.Accepted:
            return None
        ids = {listing.item(i).data(Qt.UserRole) for i in range(listing.count()) if listing.item(i).checkState() == Qt.Checked}
        return [r for r in records if r.log_id in ids]

    def _upload_directory(self, local_dir, run_id):
        token = os.getenv(TOKEN_ENV)
        if not token:
            raise RuntimeError(f"GitHub token is not configured. Set {TOKEN_ENV}; local report is preserved.")
        remote_root = f"verification/runs/{run_id}"
        for path in sorted(p for p in local_dir.rglob("*") if p.is_file()):
            rel = path.relative_to(local_dir).as_posix()
            remote_path = f"{remote_root}/{rel}"
            url = f"https://api.github.com/repos/{REPOSITORY}/contents/{remote_path}"
            payload = {
                "message": f"Add physical verification report {run_id}: {rel}",
                "content": base64.b64encode(path.read_bytes()).decode("ascii"),
            }
            request = urllib.request.Request(
                url, data=json.dumps(payload).encode("utf-8"), method="PUT",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {token}",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "Content-Type": "application/json",
                    "User-Agent": "mini4wd-physical-verification-reporter",
                },
            )
            try:
                with urllib.request.urlopen(request, timeout=30):
                    pass
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"GitHub API error {exc.code} for {remote_path}: {detail}") from exc
            except urllib.error.URLError as exc:
                raise RuntimeError(f"GitHub network error for {remote_path}: {exc.reason}") from exc
