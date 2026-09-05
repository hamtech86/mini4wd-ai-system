"""Raw Log view integrated into the existing Motor Instance Manager."""

from __future__ import annotations

from PyQt5.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from raw_log_library import RawLogLibrary


class RawLogManagerExtension:
    """Adds Instance -> Session -> Raw Log navigation without a new app."""

    def __init__(self, manager):
        self.manager = manager
        self.library = RawLogLibrary()
        self.selected_log_id = None
        self._build()

    def _build(self):
        self.page = QWidget()
        layout = QVBoxLayout(self.page)
        layout.addWidget(QLabel("Raw Logs linked to the selected Motor Instance"))

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            "log_id", "Session", "Acquired", "Firmware", "Condition", "Notes"
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.cellClicked.connect(self._select_row)
        layout.addWidget(self.table, 1)

        form = QFormLayout()
        self.notes_edit = QLineEdit()
        form.addRow("Notes", self.notes_edit)
        layout.addLayout(form)
        actions = QHBoxLayout()
        self.save_button = QPushButton("Save Metadata")
        self.save_button.clicked.connect(self._save_metadata)
        self.raw_button = QPushButton("View Raw Body")
        self.raw_button.clicked.connect(self._view_raw_body)
        actions.addWidget(self.save_button)
        actions.addWidget(self.raw_button)
        actions.addStretch()
        layout.addLayout(actions)

        self.manager.tabs.addTab(self.page, "Raw Logs")
        self.manager.instance_table.itemSelectionChanged.connect(self.refresh)
        self.refresh()

    def _current_instance_id(self):
        return getattr(self.manager, "current_instance_id", None)

    def refresh(self):
        instance_id = self._current_instance_id()
        records = []
        if instance_id is not None:
            records = [
                record
                for record in self.library.list_logs("MOTOR")
                if record.device_instance_id == str(instance_id)
            ]
        self.table.setRowCount(len(records))
        self.selected_log_id = None
        self.notes_edit.clear()
        for row, record in enumerate(records):
            values = [
                record.log_id,
                record.measurement_session_id or "",
                record.acquired_at or "",
                record.firmware_version or "",
                record.measurement_condition or "",
                record.notes or "",
            ]
            for col, value in enumerate(values):
                self.table.setItem(row, col, QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()

    def _select_row(self, row, _column):
        item = self.table.item(row, 0)
        if item is None:
            return
        self.selected_log_id = item.text()
        self.notes_edit.setText(self.table.item(row, 5).text() if self.table.item(row, 5) else "")

    def _save_metadata(self):
        if not self.selected_log_id:
            QMessageBox.information(self.manager, "Raw Log", "Raw Logを選択してください。")
            return
        try:
            self.library.update_metadata(self.selected_log_id, notes=self.notes_edit.text())
            self.refresh()
            QMessageBox.information(self.manager, "Raw Log", "Metadata updated. Raw本文とlog_idは変更されません。")
        except Exception as exc:
            QMessageBox.critical(self.manager, "Raw Log", str(exc))

    def _view_raw_body(self):
        if not self.selected_log_id:
            QMessageBox.information(self.manager, "Raw Log", "Raw Logを選択してください。")
            return
        try:
            body = self.library.read_raw(self.selected_log_id)
        except Exception as exc:
            QMessageBox.critical(self.manager, "Raw Log", str(exc))
            return

        dialog = QWidget(self.manager, windowTitle=f"Raw Body — {self.selected_log_id}")
        dialog.resize(900, 600)
        layout = QVBoxLayout(dialog)
        text = QLineEdit()
        text.setReadOnly(True)
        text.setText("Raw body is immutable. Use the library for full raw content.")
        layout.addWidget(text)
        body_view = QTableWidget(1, 1)
        body_view.setHorizontalHeaderLabels(["Raw Body (read-only)"])
        body_view.setItem(0, 0, QTableWidgetItem(body))
        body_view.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(body_view, 1)
        dialog.show()
        self._raw_dialog = dialog


def install_raw_log_manager_extension(manager):
    extension = RawLogManagerExtension(manager)
    manager.raw_log_manager_extension = extension
    return extension
