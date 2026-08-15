"""Operator-side motor instance selection and benchmark peak display."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import (
    QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QDialog, QVBoxLayout, QTableWidget, QTableWidgetItem,
)


class MotorInstanceUI:
    def __init__(self, window, context=None):
        self.window = window
        self.context = context
        self.controller = getattr(window, "breakin_controller", None)
        self.instance_selector = QComboBox()
        self.instance_label = QLabel("--")
        self.brush_peak_value = QLabel("--")
        self.brush_peak_state = QLabel("--")
        self._instances = []
        self._manager_window = None
        self._history_window = None

        root_layout = window.centralWidget().layout()
        instance_box = QGroupBox("MOTOR INSTANCE")
        instance_root = QHBoxLayout(instance_box)
        instance_form = QFormLayout()
        instance_form.addRow("Instance", self.instance_selector)
        instance_form.addRow("Selected ID", self.instance_label)
        instance_root.addLayout(instance_form, 1)

        self.manager_button = QPushButton("MANAGER")
        self.manager_button.setToolTip("Motor Instance Managerを開く")
        self.manager_button.clicked.connect(self.open_manager)
        instance_root.addWidget(self.manager_button)

        self.history_button = QPushButton("HISTORY")
        self.history_button.setToolTip("選択したMotor Instanceの保存済み結果を参照")
        self.history_button.clicked.connect(self.open_history)
        instance_root.addWidget(self.history_button)
        root_layout.insertWidget(2, instance_box)

        peak_box = QGroupBox("BENCHMARK / BRUSH PEAK")
        peak_layout = QFormLayout(peak_box)
        peak_layout.addRow("Peak Current", self.brush_peak_value)
        peak_layout.addRow("State", self.brush_peak_state)
        root_layout.insertWidget(max(0, root_layout.count() - 1), peak_box)

        self.instance_selector.currentIndexChanged.connect(self._instance_changed)
        self.timer = QTimer(window)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self.update)
        self.timer.start()
        self.load_instances()

        if self.controller is not None:
            original_benchmark = self.controller.benchmark_3v

            def benchmark_30s(*args, **kwargs):
                kwargs["duration_sec"] = max(30.0, float(kwargs.get("duration_sec", 30.0)))
                return original_benchmark(*args, **kwargs)

            self.controller.benchmark_3v = benchmark_30s

    def _database_path(self):
        return Path(__file__).resolve().parent.parent / "database" / "mini4wd.db"

    def load_instances(self):
        self.instance_selector.clear()
        self._instances = []
        path = self._database_path()
        if not path.exists():
            self.instance_selector.addItem("NO DATABASE", None)
            self.instance_label.setText("--")
            return
        try:
            connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            try:
                rows = connection.execute(
                    "SELECT instance_id, motor_model_id, serial_number, nickname, created_at "
                    "FROM motor_instance WHERE COALESCE(is_deleted, 0)=0 "
                    "ORDER BY created_at DESC, instance_id DESC"
                ).fetchall()
            finally:
                connection.close()
        except sqlite3.Error as exc:
            self.instance_selector.addItem(f"DATABASE ERROR: {exc}", None)
            return
        if not rows:
            self.instance_selector.addItem("NO ACTIVE MOTOR INSTANCE", None)
            return
        for instance_id, model_id, serial_number, nickname, created_at in rows:
            label = nickname or serial_number or f"MODEL {model_id}"
            text = f"{instance_id} / {label} / MODEL {model_id}"
            self._instances.append(instance_id)
            self.instance_selector.addItem(text, instance_id)
        self._instance_changed(0)

    def _instance_changed(self, index):
        instance_id = self.instance_selector.itemData(index)
        self.instance_label.setText(str(instance_id) if instance_id is not None else "--")
        if self.controller is not None:
            self.controller.selected_instance_id = instance_id

    def selected_instance_id(self):
        return self.instance_selector.currentData()

    def open_manager(self):
        from motor_system.python.ui.motor_manager_ui import MotorManagerUI
        self._manager_window = MotorManagerUI()
        self._manager_window.setAttribute(55, True)
        self._manager_window.show()
        self._manager_window.raise_()
        self._manager_window.activateWindow()
        self._manager_window.destroyed.connect(self.load_instances)

    def open_history(self):
        instance_id = self.selected_instance_id()
        if instance_id is None:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.information(self.window, "History", "Motor Instanceを選択してください。")
            return
        path = self._database_path()
        try:
            db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
            rows = db.execute(
                "SELECT session_id, device_type, device_model, start_datetime, end_datetime, result "
                "FROM measurement_session WHERE instance_id=? ORDER BY session_id DESC",
                (instance_id,),
            ).fetchall()
        except sqlite3.Error as exc:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.critical(self.window, "History Error", str(exc))
            return
        finally:
            try:
                db.close()
            except Exception:
                pass

        dialog = QDialog(self.window)
        dialog.setWindowTitle(f"Saved Results — Instance {instance_id}")
        dialog.resize(850, 420)
        layout = QVBoxLayout(dialog)
        table = QTableWidget(len(rows), 6)
        table.setHorizontalHeaderLabels(["Session", "Device", "Model", "Start", "End", "Result"])
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        for r, row in enumerate(rows):
            for c, value in enumerate(row):
                table.setItem(r, c, QTableWidgetItem("" if value is None else str(value)))
        table.resizeColumnsToContents()
        layout.addWidget(table)
        hint = QLabel("保存済み結果をダブルクリックすると詳細を表示します。")
        layout.addWidget(hint)

        def show_detail(row, _column):
            session_id = table.item(row, 0).text()
            from motor_system.python.ui.saved_result_dialog import SavedResultDialog
            detail = SavedResultDialog(dialog, db, session_id)
            detail.exec_()

        table.cellDoubleClicked.connect(show_detail)
        self._history_window = dialog
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    def update(self):
        controller = self.controller
        if controller is None:
            return
        measurements = list(getattr(controller, "measurements", []) or [])
        peak_values = []
        for measurement in measurements:
            if isinstance(measurement, dict):
                value = measurement.get("brush_peak_current")
            else:
                value = getattr(measurement, "brush_peak_current", None)
            try:
                if value is not None:
                    peak_values.append(float(value))
            except (TypeError, ValueError):
                pass
        peak = max(peak_values, default=float(getattr(controller, "last_brush_peak_current", 0.0) or 0.0))
        self.brush_peak_value.setText(f"{peak:.3f} A" if peak > 0 else "--")
        reached = bool(getattr(controller, "brush_peak_reached", False))
        target = float(getattr(controller, "brush_peak_target_current", 0.0) or 0.0)
        if target > 0:
            self.brush_peak_state.setText(f"APPROACH TARGET {target:.3f} A" + (" / REACHED" if reached else ""))
        elif peak > 0:
            self.brush_peak_state.setText("MEASURED / BENCHMARK")
        else:
            self.brush_peak_state.setText("NO PEAK DATA")


def install_motor_instance_ui(window, context=None):
    ui = MotorInstanceUI(window, context)
    window.motor_instance_ui = ui
    return ui
