"""Temporary raw-log paste analysis UI.

This module intentionally does not persist raw logs or depend on the Raw Log Library.
It parses existing MOTOR DATA records through the normal CSVParser -> MeasurementBuilder
pipeline and sends one selected Measurement to the existing AnalysisEngine.
"""

from PyQt5.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from communication.csv_parser import CSVParser
from communication.measurement_builder import MeasurementBuilder


class RawLogPastePanel(QGroupBox):
    """Temporary UI for analyzing pasted motor raw-log text."""

    def __init__(self, window, parent=None):
        super().__init__("TEMPORARY RAW LOG PASTE / 生ログ貼り付け解析", parent)
        self.window = window
        self.parser = CSVParser()
        self.builder = MeasurementBuilder()
        self.measurements = []

        root = QVBoxLayout(self)
        root.addWidget(QLabel(
            "※一時機能：貼り付けた原文は保存・変更しません。"
            " DATA 行だけを既存解析系へ渡します。"
        ))

        self.editor = QPlainTextEdit()
        self.editor.setPlaceholderText("Motor raw log をここへ貼り付けてください")
        self.editor.setMinimumHeight(140)
        root.addWidget(self.editor)

        actions = QHBoxLayout()
        self.analyze_button = QPushButton("貼り付けログを解析")
        self.clear_button = QPushButton("クリア")
        self.data_selector = QComboBox()
        self.data_selector.setEnabled(False)
        self.data_selector.currentIndexChanged.connect(self._selection_changed)
        self.analyze_button.clicked.connect(self.parse_log)
        self.clear_button.clicked.connect(self.clear)
        actions.addWidget(self.analyze_button)
        actions.addWidget(self.clear_button)
        actions.addWidget(QLabel("解析 DATA:"))
        actions.addWidget(self.data_selector, 1)
        root.addLayout(actions)

        self.status = QLabel("DATA rows: 0")
        root.addWidget(self.status)

    def parse_log(self):
        """Parse only valid DATA lines; keep the pasted text untouched."""
        self.measurements = []
        self.data_selector.clear()
        invalid = 0

        for line_number, raw_line in enumerate(self.editor.toPlainText().splitlines(), 1):
            if not raw_line.strip().startswith("DATA,"):
                continue
            try:
                data = self.parser.parse(raw_line)
                if not self.parser.is_data_record(data):
                    continue
                measurement = self.builder.build(data)
                self.measurements.append((line_number, measurement))
            except (TypeError, ValueError, OverflowError):
                invalid += 1

        for index, (line_number, measurement) in enumerate(self.measurements, 1):
            self.data_selector.addItem(
                f"#{index}  line {line_number}  "
                f"t={measurement.elapsed_time} ms  "
                f"V={measurement.motor_voltage:.3f} V  "
                f"I={measurement.current_avg:.3f} A",
                index - 1,
            )

        self.data_selector.setEnabled(bool(self.measurements))
        self.status.setText(
            f"DATA rows: {len(self.measurements)}"
            + (f" / invalid DATA: {invalid}" if invalid else "")
        )

        if not self.measurements:
            QMessageBox.warning(
                self,
                "Raw Log",
                "有効な Motor DATA 行が見つかりません。"
            )
            return

        self._analyze_selected()

    def _selection_changed(self, _index):
        if self.measurements:
            self._analyze_selected()

    def _analyze_selected(self):
        index = self.data_selector.currentData()
        if index is None or not (0 <= index < len(self.measurements)):
            return
        _, measurement = self.measurements[index]
        try:
            analysis = self.window.analysis_engine.analyze(
                measurement,
                self.window._selected_motor_spec(),
            )
            performance = analysis.performance
            result = getattr(self.window, "estimated_result", {})
            values = {
                "RPM_3V": f"{performance.estimated_rpm_3v.value:.0f} rpm",
                "RPM_28V": f"{performance.estimated_rpm_28v.value:.0f} rpm",
                "TORQUE_3V": f"{performance.estimated_torque_3v.value:.2f} g·cm",
                "TORQUE_28V": f"{performance.estimated_torque_28v.value:.2f} g·cm",
                "WEIGHT": f"{performance.estimated_supported_weight.value:.0f} g",
            }
            for key, text in values.items():
                if key in result:
                    result[key].setText(text)
            self.status.setText(
                f"DATA rows: {len(self.measurements)} / "
                f"selected: {index + 1}"
            )
        except Exception as exc:
            self.status.setText(f"Analysis ERROR: {exc}")

    def clear(self):
        self.editor.clear()
        self.measurements = []
        self.data_selector.clear()
        self.data_selector.setEnabled(False)
        self.status.setText("DATA rows: 0")


def install_raw_log_paste_ui(window):
    """Install the temporary panel into the existing motor-page layout."""
    content = getattr(window, "motor_content", None)
    layout = content.layout() if content is not None else None
    if layout is None:
        return None
    panel = RawLogPastePanel(window, content)
    layout.addWidget(panel)
    window.raw_log_paste_panel = panel
    return panel
