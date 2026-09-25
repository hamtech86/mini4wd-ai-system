"""Database-style manager for the complete Local RawLog Library.

This screen manages existing RawLogs without changing raw bodies, IDs, or
measurement sessions. Editable metadata remains limited to fields already
supported by RawLogLibrary.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt, QDate
from PyQt5.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QFormLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QInputDialog,
)

from raw_log_library import RawLogLibrary
from raw_log_library.github_export import GitHubRawLogExporter, GitHubRegistrationError
from ui.instance_visibility import InstanceVisibilityStore


class RawLogDatabaseManager(QDialog):
    """Manage all Local RawLogs; never edits raw body/log_id/session_id."""

    HEADERS = [
        "Session", "Acquired", "Type", "RawLog", "Instance", "Benchmark Type",
        "Condition", "Note", "GitHub", "Instance Visibility", "Integrity",
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        root = Path(__file__).resolve().parents[1]
        self.library = RawLogLibrary(root / "data" / "raw_logs")
        self.visibility = InstanceVisibilityStore(root / "data" / "instance_manager")
        self.records = []
        self.setWindowTitle("RawLog Database Manager")
        self.resize(1500, 850)
        self._build()
        self.refresh()

    def _build(self):
        root = QVBoxLayout(self)

        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Session / RawLog / Instance / Note")
        self.search.textChanged.connect(self.refresh)
        filters.addWidget(self.search)

        self.type_filter = QComboBox()
        self.type_filter.addItems(["Type: ALL", "MOTOR", "BATTERY"])
        self.type_filter.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.type_filter)

        self.instance_filter = QLineEdit()
        self.instance_filter.setPlaceholderText("Instance: ALL")
        self.instance_filter.textChanged.connect(self.refresh)
        filters.addWidget(self.instance_filter)

        self.benchmark_filter = QLineEdit()
        self.benchmark_filter.setPlaceholderText("Benchmark Type: ALL")
        self.benchmark_filter.textChanged.connect(self.refresh)
        filters.addWidget(self.benchmark_filter)

        self.github_filter = QComboBox()
        self.github_filter.addItems(["GitHub: ALL", "REGISTERED", "UNREGISTERED"])
        self.github_filter.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.github_filter)

        self.visibility_filter = QComboBox()
        self.visibility_filter.addItems(["Visibility: ALL", "VISIBLE", "HIDDEN"])
        self.visibility_filter.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.visibility_filter)

        self.integrity_filter = QComboBox()
        self.integrity_filter.addItems(["Integrity: ALL", "OK", "ERROR"])
        self.integrity_filter.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.integrity_filter)

        self.start_date = QDateEdit()
        self.start_date.setCalendarPopup(True)
        self.start_date.setSpecialValueText("Start: ALL")
        self.start_date.setDate(QDate(2000, 1, 1))
        self.start_date.dateChanged.connect(self.refresh)
        filters.addWidget(self.start_date)

        self.end_date = QDateEdit()
        self.end_date.setCalendarPopup(True)
        self.end_date.setDate(QDate.currentDate())
        self.end_date.dateChanged.connect(self.refresh)
        filters.addWidget(self.end_date)

        root.addLayout(filters)

        root.addWidget(QLabel("Session順を基本表示。列ヘッダークリックでソートできます。"))
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSortingEnabled(True)
        root.addWidget(self.table, 1)

        actions = QHBoxLayout()
        for label, slot in [
            ("Edit Note", self.edit_note),
            ("Relink Instance", self.relink_instance),
            ("Set Instance VISIBLE", lambda: self.set_instance_visibility("VISIBLE")),
            ("Set Instance HIDDEN", lambda: self.set_instance_visibility("HIDDEN")),
            ("GitHub Register", self.register_github),
            ("View Raw Body", self.view_raw_body),
            ("Refresh", self.refresh),
        ]:
            button = QPushButton(label)
            button.clicked.connect(slot)
            actions.addWidget(button)
        actions.addStretch()
        root.addLayout(actions)

    def _selected_log_id(self):
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        item = self.table.item(rows[0].row(), 3)
        return item.data(Qt.UserRole) if item else None

    def _record_integrity(self, record):
        try:
            _, raw_path, metadata_path = self.library.get(record.log_id)
            if not raw_path.exists() or not metadata_path.exists():
                return "ERROR"
            return "OK"
        except Exception:
            return "ERROR"

    def _date_key(self, value):
        if not value:
            return datetime.min
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return datetime.min

    def _passes_filters(self, record):
        haystack = " ".join([
            str(record.measurement_session_id or ""),
            str(record.log_id or ""),
            str(record.device_instance_id or ""),
            str(record.motor_id or ""),
            str(record.battery_id or ""),
            str(record.notes or ""),
        ]).lower()
        query = self.search.text().strip().lower()
        if query and query not in haystack:
            return False

        kind = self.type_filter.currentText()
        if kind != "Type: ALL" and record.device_type.upper() != kind:
            return False

        instance = self.instance_filter.text().strip().lower()
        if instance and instance != "all":
            if instance not in str(record.device_instance_id or "").lower():
                return False

        benchmark = self.benchmark_filter.text().strip().lower()
        if benchmark and benchmark != "all":
            if benchmark not in str(record.measurement_condition or "").lower():
                return False

        github = self.library.get_github_status(record.log_id).get("status", "UNREGISTERED")
        github_filter = self.github_filter.currentText().split(": ", 1)[-1]
        if github_filter != "ALL" and github != github_filter:
            return False

        visibility_filter = self.visibility_filter.currentText().split(": ", 1)[-1]
        if visibility_filter != "ALL":
            iid = record.device_instance_id
            if iid is None or self.visibility.get(iid) != visibility_filter:
                return False

        integrity_filter = self.integrity_filter.currentText().split(": ", 1)[-1]
        if integrity_filter != "ALL" and self._record_integrity(record) != integrity_filter:
            return False

        acquired = self._date_key(record.acquired_at).date()
        if acquired < self.start_date.date().toPyDate() or acquired > self.end_date.date().toPyDate():
            return False
        return True

    def refresh(self):
        self.table.setSortingEnabled(False)
        try:
            self.records = list(self.library.list_logs())
            filtered = [r for r in self.records if self._passes_filters(r)]
            # Session順 → Acquired順. Empty Session values remain last.
            filtered.sort(
                key=lambda r: (
                    str(r.measurement_session_id or "~~~~"),
                    self._date_key(r.acquired_at),
                )
            )
            self.table.setRowCount(len(filtered))
            for row, record in enumerate(filtered):
                github = self.library.get_github_status(record.log_id).get("status", "UNREGISTERED")
                iid = record.device_instance_id or ""
                visibility = self.visibility.get(iid) if iid else "—"
                integrity = self._record_integrity(record)
                values = [
                    record.measurement_session_id or "",
                    record.acquired_at or "",
                    record.device_type or "",
                    record.log_id,
                    iid,
                    record.measurement_condition or "",
                    "—",
                    record.notes or "",
                    github,
                    visibility,
                    integrity,
                ]
                for col, value in enumerate(values):
                    item = QTableWidgetItem(str(value))
                    if col == 3:
                        item.setData(Qt.UserRole, record.log_id)
                    self.table.setItem(row, col, item)
            self.table.resizeColumnsToContents()
        finally:
            self.table.setSortingEnabled(True)

    def _selected_record(self):
        log_id = self._selected_log_id()
        if not log_id:
            return None
        try:
            return self.library.get(log_id)[0]
        except KeyError:
            return None

    def edit_note(self):
        record = self._selected_record()
        if not record:
            return
        value, ok = QInputDialog.getText(
            self, "RawLog Note", "Note:", text=record.notes or ""
        )
        if not ok:
            return
        try:
            self.library.update_metadata(record.log_id, notes=value)
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Note", str(exc))

    def relink_instance(self):
        record = self._selected_record()
        if not record:
            return
        if record.device_type.upper() != "MOTOR":
            QMessageBox.information(self, "Instance", "Battery RawLogにはMotor Instance紐付けはありません。")
            return
        current = str(record.device_instance_id or "")
        value, ok = QInputDialog.getText(
            self, "Relink Instance", "Target Instance ID:", text=current
        )
        if not ok or not value.strip() or value.strip() == current:
            return
        target = value.strip()
        session_logs = self.library.list_by_session(str(record.measurement_session_id)) if record.measurement_session_id else []
        details = [
            f"RawLog: {record.log_id}",
            f"Current Instance: {current or '—'}",
            f"Target Instance: {target}",
            f"Session: {record.measurement_session_id or '—'}",
            "同一Session RawLogs: " + ", ".join(
                f"{x.log_id}:{x.device_instance_id or '—'}" for x in session_logs
            ),
        ]
        if QMessageBox.question(
            self, "Relink Instance — Confirm",
            "\n".join(details) + "\n\n関連付けだけを変更しますか？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        ) != QMessageBox.Yes:
            return
        try:
            self.library.update_metadata(record.log_id, device_instance_id=target)
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Relink", str(exc))

    def set_instance_visibility(self, value):
        record = self._selected_record()
        if not record or not record.device_instance_id:
            return
        try:
            self.visibility.set(record.device_instance_id, value)
            self.refresh()
        except Exception as exc:
            QMessageBox.critical(self, "Visibility", str(exc))

    def register_github(self):
        record = self._selected_record()
        if not record:
            return
        try:
            status = self.library.get_github_status(record.log_id)
            if status.get("status") == "REGISTERED":
                QMessageBox.information(self, "GitHub", f"{record.log_id} は既にGitHub登録済みです。")
                return
            answer = QMessageBox.question(
                self, "GitHub登録",
                f"{record.log_id}\nSession: {record.measurement_session_id or '—'}\n"
                f"Instance: {record.device_instance_id or '—'}\n"
                f"Benchmark: {record.measurement_condition or '—'}\n\n"
                "Local RawLogをGitHubへ登録しますか？",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if answer != QMessageBox.Yes:
                return
            result = GitHubRawLogExporter(self.library).register(record.log_id)
            self.refresh()
            QMessageBox.information(
                self, "GitHub",
                f"登録完了\n{result.get('repository', '')}\n{result.get('raw_path', '')}",
            )
        except GitHubRegistrationError as exc:
            self.refresh()
            QMessageBox.critical(self, "GitHub登録失敗", str(exc))
        except Exception as exc:
            self.refresh()
            QMessageBox.critical(self, "GitHub登録失敗", str(exc))

    def view_raw_body(self):
        record = self._selected_record()
        if not record:
            return
        try:
            body = self.library.read_raw(record.log_id)
        except Exception as exc:
            QMessageBox.critical(self, "RawLog", str(exc))
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Raw Body — {record.log_id}")
        dialog.resize(1000, 700)
        layout = QVBoxLayout(dialog)
        from PyQt5.QtWidgets import QPlainTextEdit
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setLineWrapMode(QPlainTextEdit.NoWrap)
        view.setPlainText(body)
        layout.addWidget(view)
        dialog.exec_()


def open_raw_log_database_manager(parent=None):
    dialog = RawLogDatabaseManager(parent)
    dialog.exec_()
