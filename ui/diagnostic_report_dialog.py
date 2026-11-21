"""Operator dialog for creating shared Battery/Motor diagnostic reports."""
from __future__ import annotations

from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMessageBox, QPushButton, QVBoxLayout,
)

from diagnostic_report import DiagnosticReportError, DiagnosticReportService
from raw_log_library import RawLogLibrary


class DiagnosticReportDialog(QDialog):
    def __init__(self, parent, library: RawLogLibrary, report_root: str | Path = "data/diagnostic_reports"):
        super().__init__(parent)
        self.window = parent
        self.library = library
        self.report_root = report_root
        self.setWindowTitle("SHARED DIAGNOSTIC REPORT")
        self.resize(620, 520)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Device type"))
        self.device_type = QComboBox()
        self.device_type.addItems(["BATTERY", "MOTOR"])
        self.device_type.currentTextChanged.connect(self.refresh_logs)
        layout.addWidget(self.device_type)

        layout.addWidget(QLabel("Select RawLogs to include (multi-select by checkbox; no automatic selection)"))
        self.logs = QListWidget()
        layout.addWidget(self.logs, 1)

        layout.addWidget(QLabel("GitHub token (optional; kept in this dialog session only)"))
        self.token = QLineEdit()
        self.token.setEchoMode(QLineEdit.Password)
        self.token.setPlaceholderText("Leave blank to create a local-only report")
        layout.addWidget(self.token)

        actions = QHBoxLayout()
        self.refresh_button = QPushButton("REFRESH")
        self.refresh_button.clicked.connect(self.refresh_logs)
        actions.addWidget(self.refresh_button)
        self.create_button = QPushButton("CREATE LOCAL REPORT / UPLOAD")
        self.create_button.clicked.connect(self.create_report)
        actions.addWidget(self.create_button)
        layout.addLayout(actions)
        self.status = QLabel("Select one or more RawLogs. Original RawLog bodies are copied without modification.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.refresh_logs()

    def refresh_logs(self):
        kind = self.device_type.currentText()
        self.logs.clear()
        try:
            records = self.library.list_logs(kind)
            for record in records:
                channel = f" / {record.channel}" if record.channel else ""
                instance = f" / Instance {record.device_instance_id}" if record.device_instance_id else " / no Instance"
                item = QListWidgetItem(f"{record.log_id}{channel}{instance} / {record.acquired_at or 'time unknown'}")
                item.setData(Qt.UserRole, record.log_id)
                item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
                item.setCheckState(Qt.Unchecked)
                self.logs.addItem(item)
            self.status.setText(f"{len(records)} {kind} RawLog(s) available. Nothing is selected automatically.")
        except Exception as exc:
            self.status.setText(f"RawLog listing failed: {type(exc).__name__}: {exc}")

    def create_report(self):
        selected = [
            self.logs.item(index).data(Qt.UserRole)
            for index in range(self.logs.count())
            if self.logs.item(index).checkState() == Qt.Checked
        ]
        if not selected:
            QMessageBox.warning(self, "Diagnostic Report", "Select at least one RawLog.")
            return

        window = self.window
        ui_events = window.ui_log.toPlainText() if hasattr(window, "ui_log") else ""
        error_code = getattr(window, "_ui_error_code", None)
        error_message = getattr(window, "_ui_error_message", None)
        context = {
            "database_available": bool(getattr(window, "database_available", False)),
            "anonymous_mode": not bool(getattr(window, "database_available", False)),
        }
        instance_widget = getattr(window, "instance", None)
        if instance_widget is not None and callable(getattr(instance_widget, "currentData", None)):
            context["motor_instance_id"] = instance_widget.currentData()
        battery_tab = getattr(window, "battery_tab", None)
        if battery_tab is not None:
            context["battery_anonymous_mode"] = bool(getattr(battery_tab, "anonymous_mode", False))

        service = DiagnosticReportService(
            self.library, report_root=self.report_root,
            token=self.token.text().strip() or None,
        )
        try:
            bundle = service.create_local_bundle(
                self.device_type.currentText(), selected,
                ui_events=ui_events, error_code=error_code,
                error_message=error_message, context=context,
            )
            token = self.token.text().strip()
            self.token.clear()
            if not token:
                self.status.setText(f"LOCAL REPORT SAVED. GitHub upload skipped.\n{bundle}")
                QMessageBox.information(self, "Diagnostic Report", f"Local report saved:\n{bundle}")
                return
            result = service.upload_bundle(bundle)
            self.status.setText(f"UPLOAD COMPLETE: {result['repository']}\n{bundle}")
            QMessageBox.information(self, "Diagnostic Report", f"Report uploaded. Local copy retained:\n{bundle}")
        except (DiagnosticReportError, Exception) as exc:
            local = getattr(exc, "local_bundle", None)
            suffix = f"\nLocal recovery bundle: {local}" if local else ""
            self.status.setText(f"REPORT NOT FULLY UPLOADED: {type(exc).__name__}: {exc}{suffix}")
            QMessageBox.warning(self, "Diagnostic Report", f"{exc}{suffix}")
        finally:
            self.token.clear()
