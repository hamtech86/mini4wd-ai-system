"""Operator-side motor instance selection and benchmark peak display.

This module augments MainWindow without coupling the core break-in controller
or recipe engine to Qt widgets.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QComboBox, QFormLayout, QGroupBox, QLabel


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

        root_layout = window.centralWidget().layout()
        instance_box = QGroupBox("MOTOR INSTANCE")
        instance_layout = QFormLayout(instance_box)
        instance_layout.addRow("Instance", self.instance_selector)
        instance_layout.addRow("Selected ID", self.instance_label)
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
                    "SELECT instance_id, motor_model_id, created_at "
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

        for instance_id, model_id, created_at in rows:
            text = f"{instance_id} / MODEL {model_id} / {created_at or '-'}"
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
            self.brush_peak_state.setText(
                f"APPROACH TARGET {target:.3f} A" + (" / REACHED" if reached else "")
            )
        elif peak > 0:
            self.brush_peak_state.setText("MEASURED / BENCHMARK")
        else:
            self.brush_peak_state.setText("NO PEAK DATA")


def install_motor_instance_ui(window, context=None):
    """Install operator widgets and retain the augmentation on the window."""
    ui = MotorInstanceUI(window, context)
    window.motor_instance_ui = ui
    return ui
