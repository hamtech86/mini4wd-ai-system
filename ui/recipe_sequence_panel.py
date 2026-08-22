"""Reusable PyQt5 editor for declarative break-in recipe sequences.

The panel exposes an operator-facing preset selector and ordered sequence
selection. Hardware execution remains outside the widget.
"""

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QVBoxLayout, QWidget
)


class RecipeSequencePanel(QGroupBox):
    """Preset selector + ordered, checkbox-enabled sequence list."""

    enabled_changed = pyqtSignal(object)
    preset_loaded = pyqtSignal(str)
    execute_requested = pyqtSignal(str, object)
    stop_requested = pyqtSignal()

    def __init__(self, recipe_engine, parent=None):
        super().__init__("RECIPE / SEQUENCE", parent)
        self.recipe_engine = recipe_engine
        self._checks = []
        root = QVBoxLayout(self)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("プリセット"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(self.recipe_engine.names())
        self.preset_combo.currentTextChanged.connect(self.load_preset)
        toolbar.addWidget(self.preset_combo, 1)
        self.load_button = QPushButton("読み込み")
        self.load_button.clicked.connect(lambda: self.load_preset(self.preset_combo.currentText()))
        toolbar.addWidget(self.load_button)
        root.addLayout(toolbar)

        selection_toolbar = QHBoxLayout()
        self.select_all = QPushButton("全選択")
        self.select_none = QPushButton("全解除")
        self.select_all.clicked.connect(lambda: self._set_all(True))
        self.select_none.clicked.connect(lambda: self._set_all(False))
        selection_toolbar.addWidget(self.select_all)
        selection_toolbar.addWidget(self.select_none)
        selection_toolbar.addStretch()
        self.execute_button = QPushButton("選択Sequenceを実行")
        self.stop_button = QPushButton("Sequence停止")
        self.stop_button.setEnabled(False)
        self.execute_button.clicked.connect(self._request_execute)
        self.stop_button.clicked.connect(self.stop_requested.emit)
        selection_toolbar.addWidget(self.execute_button)
        selection_toolbar.addWidget(self.stop_button)
        root.addLayout(selection_toolbar)

        self.status_label = QLabel("未実行")
        root.addWidget(self.status_label)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(1)
        self.body = QWidget()
        self.form = QFormLayout(self.body)
        self.form.setVerticalSpacing(5)
        self.scroll.setWidget(self.body)
        root.addWidget(self.scroll, 1)

        if self.preset_combo.count():
            self.load_preset(self.preset_combo.currentText())

    def load_preset(self, recipe_name):
        while self.form.count():
            item = self.form.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self._checks = []
        recipe = self.recipe_engine.get(recipe_name)
        if recipe is None:
            self.preset_loaded.emit("")
            self.status_label.setText("レシピが見つかりません")
            return
        for sequence in recipe.sequences():
            check = QCheckBox()
            check.setChecked(sequence.enabled)
            detail = self._detail(sequence)
            check.stateChanged.connect(self._emit_enabled)
            row = QWidget()
            layout = QHBoxLayout(row)
            layout.setContentsMargins(2, 2, 2, 2)
            layout.addWidget(check)
            layout.addWidget(QLabel(detail), 1)
            self.form.addRow(row)
            self._checks.append((sequence.sequence_id, check))
        self.preset_loaded.emit(recipe.name)
        self._emit_enabled()
        self.status_label.setText(f"{recipe.name}: {len(self._checks)} Sequence")

    @staticmethod
    def _detail(sequence):
        parts = [f"{sequence.order:02d}", sequence.sequence_id, sequence.command]
        if sequence.direction:
            parts.append(sequence.direction)
        if sequence.pwm is not None:
            parts.append(f"PWM {sequence.pwm}")
        if sequence.duration_sec is not None:
            parts.append(f"{sequence.duration_sec:g}s")
        if sequence.conditions:
            parts.append("条件=" + ",".join(f"{c.metric}{c.operator}{c.value:g}" for c in sequence.conditions))
        return " | ".join(parts)

    def _set_all(self, checked):
        for _, checkbox in self._checks:
            checkbox.blockSignals(True)
            checkbox.setChecked(checked)
            checkbox.blockSignals(False)
        self._emit_enabled()

    def _emit_enabled(self):
        self.enabled_changed.emit(self.enabled_ids())

    def enabled_ids(self):
        return {sid for sid, checkbox in self._checks if checkbox.isChecked()}

    def _request_execute(self):
        recipe_name = self.preset_combo.currentText().strip()
        if not recipe_name:
            return
        self.execute_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.status_label.setText(f"実行準備: {recipe_name}")
        self.execute_requested.emit(recipe_name, self.enabled_ids())

    def set_execution_state(self, running, text=None):
        self.execute_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        if text:
            self.status_label.setText(text)
