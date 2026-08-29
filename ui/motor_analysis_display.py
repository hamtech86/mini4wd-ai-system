"""Reusable Qt display for measured 3.0 V and projected 2.8 V motor results."""
from PyQt5.QtWidgets import QFormLayout, QGroupBox, QLabel, QVBoxLayout, QWidget


class MotorVoltageResultWidget(QGroupBox):
    """Display measured 3 V and projected 2.8 V values side by side."""

    def __init__(self, parent=None):
        super().__init__("MOTOR ANALYSIS — 3.0V / 2.8V", parent)
        root = QVBoxLayout(self)
        self.status = QLabel("--")
        self.measured = {}
        self.projected = {}
        for title, target in (("3.0V 実測", self.measured), ("2.8V 換算", self.projected)):
            box = QGroupBox(title)
            form = QFormLayout(box)
            for key, label in (("voltage", "モーター電圧"), ("rpm", "RPM"), ("current", "電流"), ("power", "電力")):
                value = QLabel("--")
                target[key] = value
                form.addRow(label + ":", value)
            root.addWidget(box)
        root.addWidget(QLabel("3V到達判定:"))
        root.addWidget(self.status)

    def set_values(self, measured_voltage=None, measured_rpm=None,
                   measured_current=None, measured_power=None,
                   projected_rpm=None, projected_current=None,
                   projected_power=None, reached_3v=False):
        self.measured["voltage"].setText(self._fmt(measured_voltage, " V"))
        self.measured["rpm"].setText(self._fmt(measured_rpm, " rpm", 0))
        self.measured["current"].setText(self._fmt(measured_current, " A", 3))
        self.measured["power"].setText(self._fmt(measured_power, " W", 3))
        self.projected["voltage"].setText("2.80 V")
        self.projected["rpm"].setText(self._fmt(projected_rpm, " rpm", 0))
        self.projected["current"].setText(self._fmt(projected_current, " A", 3))
        self.projected["power"].setText(self._fmt(projected_power, " W", 3))
        self.status.setText("3.00 V 到達 / 実測あり" if reached_3v else "3.00 V 未到達 / 3V実測値なし")

    @staticmethod
    def _fmt(value, suffix="", decimals=2):
        if value is None:
            return "--"
        return f"{float(value):.{decimals}f}{suffix}"
