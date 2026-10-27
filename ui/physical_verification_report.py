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
    QComboBox, QDialog, QDialogButtonBox, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QVBoxLayout, QInputDialog, QLineEdit,
    QFormLayout, QPlainTextEdit,
)

from raw_log_library import RawLogLibrary

REPOSITORY = "hamtech86/mini4wd-raw-logs"
TOKEN_ENV = "MINI4WD_GITHUB_TOKEN"
PHYSICAL_STOP_CHOICES = (
    ("未確認", "unconfirmed"),
    ("測定終了後に停止を確認", "confirmed_after_measurement"),
    ("Stop押下時に停止を確認", "confirmed_after_stop_button"),
    ("その他の方法で停止を確認", "confirmed_other"),
)


def _safe(value):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "unknown")).strip("._") or "unknown"


def _physical_stop_record(observation, recorded_at):
    """Serialize the operator's physical observation without inferring a result."""
    return {
        "status": observation["status"],
        "status_label": observation["status_label"],
        "details": observation.get("details", ""),
        "recorded_at_utc": recorded_at.isoformat(),
        "source": "operator_input_before_upload",
    }


def _record_observation_in_ui_history(window, timestamped_lines):
    """Mirror the recorded observation in the visible UI history."""
    if hasattr(window, "ui_log"):
        window.ui_log.appendPlainText("\\n".join(timestamped_lines))


def _identity_snapshot(controller, history):
    """Represent current identity state and preserve a successful INFO event in this session."""
    controller_verified = (
        controller is not None
        and getattr(controller, "identity_verified", False) is True
    )
    history_verified = bool(re.search(r"Motor INFO identity verified:", history or ""))
    verified = controller_verified or history_verified
    evidence = (
        "controller_state" if controller_verified
        else "ui_history" if history_verified
        else "unverified_or_unavailable"
    )
    identity = {"identity_verified": verified, "identity_evidence": evidence}
    if controller is not None:
        for key in ("firmware_version", "device_model", "device_id", "build"):
            value = getattr(controller, key, None)
            if value is not None:
                identity[key] = value
        info = getattr(controller, "device_info", {}) or {}
        for source, target in (("FW", "firmware_version"), ("MODEL", "device_model"),
                               ("ID", "device_id"), ("BUILD", "build")):
            if target not in identity and info.get(source) is not None:
                identity[target] = info[source]
    return identity


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

        physical_observation = self._collect_physical_observation()
        if physical_observation is None:
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

        history = self.window.ui_log.toPlainText() if hasattr(self.window, "ui_log") else ""
        observation_status = physical_observation["status"]
        observation_label = physical_observation["status_label"]
        observation_details = physical_observation["details"]
        history_lines = [
            f"Physical stop observation recorded before report upload: {observation_label}.",
        ]
        if observation_details:
            history_lines.append(f"Physical observation details: {observation_details}")
        timestamped_observation_lines = [
            f"[{now.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')}] {line}"
            for line in history_lines
        ]
        history = (history.rstrip() + "\n" if history.strip() else "") + "\n".join(
            timestamped_observation_lines
        ) + "\n"
        # Keep the visible in-session UI history consistent with report.json and
        # ui-history.log. This records the operator's observation, not a STOP ACK.
        if hasattr(self.window, "ui_log"):
            self.window.ui_log.appendPlainText("\n".join(timestamped_observation_lines))

        identity = _identity_snapshot(controller, history)
        error_code = getattr(self.window, "_ui_error_code", None)
        error_message = getattr(self.window, "_ui_error_message", None)
        report = {
            "verification_run_id": run_id,
            "created_at_utc": now.isoformat(),
            "repository": REPOSITORY,
            "motor_instance_id": str(instance_id),
            "recipe": recipe,
            "device_identity": identity,
            "physical_stop_observation": _physical_stop_record(physical_observation, now),
            "error": {"code": error_code, "message": error_message},
            "included_raw_log_ids": [r.log_id for r in selected],
            "notes": "Physical stop status is the operator's explicit observation. INFO identity evidence may come from the current controller state or a successful INFO event in this UI session. CI/source status is not physical verification.",
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
            (raw_dir / f"{_safe(record.log_id)}.metadata.json").write_text(
                json.dumps({
                    "log_id": record.log_id,
                    "device_type": record.device_type,
                    "device_model": record.device_model,
                    "firmware_version": record.firmware_version,
                    "device_instance_id": record.device_instance_id,
                    "measurement_session_id": record.measurement_session_id,
                    "acquired_at": record.acquired_at,
                    "measurement_condition": record.measurement_condition,
                    "source_reference": record.source_reference,
                    "notes": record.notes,
                }, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        preview = (
            f"Verification run: {run_id}\nInstance: {instance_id}\nRecipe: {recipe or '--'}\n"
            f"Physical stop: {observation_label}\nDetails: {observation_details or '--'}\n"
            f"RawLogs: {', '.join(r.log_id for r in selected) if selected else '(none selected)'}\n"
            f"Local recovery copy: {local_dir}\n\nGitHubへ送信しますか？"
        )
        if QMessageBox.question(
            self.window, "Send Verification Report — Confirm", preview,
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        ) != QMessageBox.Yes:
            QMessageBox.information(self.window, "Verification report saved", f"送信せずローカル保存しました。\n{local_dir}")
            return

        token = getattr(self.window, "_physical_verification_token", None) or os.getenv(TOKEN_ENV)
        if not token:
            token, accepted = QInputDialog.getText(
                self.window,
                "GitHub Token",
                "RawLogリポジトリへの書き込み権限を持つGitHubトークンを入力してください。\n"
                "入力内容は画面上で伏せ字になり、このアプリの実行中だけ保持されます。",
                QLineEdit.Password,
            )
            if not accepted or not token.strip():
                QMessageBox.information(
                    self.window, "Verification report saved",
                    f"トークンが入力されなかったため送信しませんでした。ローカル保存は残っています。\n{local_dir}",
                )
                return
            token = token.strip()
            self.window._physical_verification_token = token

        try:
            self._upload_directory(local_dir, run_id, token=token)
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

    def _collect_physical_observation(self):
        dialog = QDialog(self.window)
        dialog.setWindowTitle("実機停止の確認記録")
        dialog.resize(560, 260)
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel(
            "実機を目視等で確認した結果を記録してください。ソフトウェアのSTOP要求だけでは"
            "「停止を確認」とは扱いません。未確認の場合もそのまま記録できます。"
        ))
        form = QFormLayout()
        status = QComboBox()
        for label, value in PHYSICAL_STOP_CHOICES:
            status.addItem(label, value)
        details = QPlainTextEdit()
        details.setPlaceholderText("任意：対象モーター、確認時刻、操作など")
        details.setMaximumHeight(90)
        form.addRow("実機停止結果", status)
        form.addRow("補足", details)
        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec_() != QDialog.Accepted:
            return None
        value = status.currentData()
        label = status.currentText()
        note = details.toPlainText().strip()
        if value != "unconfirmed" and not note:
            QMessageBox.warning(
                self.window, "実機停止の確認記録",
                "停止を確認した場合は、対象モーターと確認内容を補足欄に記入してください。",
            )
            return None
        return {"status": value, "status_label": label, "details": note}

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

    def _upload_directory(self, local_dir, run_id, token=None):
        token = token or getattr(getattr(self, "window", None), "_physical_verification_token", None) or os.getenv(TOKEN_ENV)
        if not token:
            raise RuntimeError(f"GitHub token is not configured. Enter it in the UI or set {TOKEN_ENV}; local report is preserved.")
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
