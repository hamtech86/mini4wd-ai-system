"""PyQt5 operator UI for 2-channel 5 A battery discharge."""
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit,
    QMainWindow, QMessageBox, QPushButton, QPlainTextEdit, QVBoxLayout, QWidget,
)

from battery_system.serial import BatterySample, BatterySerial


class BatteryChannelCard(QGroupBox):
    def __init__(self, channel):
        super().__init__(f"CH{channel} / 5A DISCHARGE")
        self.channel = channel
        grid = QGridLayout(self)
        self.values = {}
        fields = (
            ("STATE", "state"),
            ("VOLTAGE", "voltage"),
            ("CURRENT", "current"),
            ("PWM", "pwm"),
            ("ELAPSED", "elapsed"),
            ("TARGET", "target"),
            ("ATTAINMENT", "attainment"),
            ("INTERNAL R", "internal_r"),
        )
        for row, (title, key) in enumerate(fields):
            grid.addWidget(QLabel(title), row, 0)
            value = QLabel("--")
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value.setStyleSheet("font-size:16px;font-weight:bold;")
            grid.addWidget(value, row, 1)
            self.values[key] = value

    def set_sample(self, sample: BatterySample, target=5.0):
        self.values["state"].setText(sample.state or "RUN")
        self.values["voltage"].setText("--" if sample.voltage is None else f"{sample.voltage:.3f} V")
        self.values["current"].setText("--" if sample.current is None else f"{sample.current:.3f} A")
        self.values["pwm"].setText("--" if sample.pwm is None else str(sample.pwm))
        self.values["elapsed"].setText("--" if sample.elapsed_sec is None else f"{sample.elapsed_sec:.1f} s")
        self.values["target"].setText(f"{target:.2f} A")
        if sample.current is None or target <= 0:
            self.values["attainment"].setText("--")
        else:
            self.values["attainment"].setText(f"{sample.current / target * 100:.1f} %")
        # Internal resistance is intentionally unavailable until a controlled
        # load-step/recovery measurement is implemented in the evaluation layer.
        self.values["internal_r"].setText("-- mΩ")

    def set_state(self, state):
        self.values["state"].setText(state)


class BatteryEvaluationWindow(QMainWindow):
    TARGET_CURRENT = 5.0

    def __init__(self, port="/dev/ttyACM0", parent=None):
        super().__init__(parent)
        self.transport = BatterySerial(port=port)
        self.cards = {1: BatteryChannelCard(1), 2: BatteryChannelCard(2)}
        self._build_ui()
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.poll_serial)
        self._set_all_state("READY")

    def _build_ui(self):
        self.setWindowTitle("MINI4WD AI SYSTEM - BATTERY 5A EVALUATION")
        self.resize(760, 720)
        root = QWidget()
        layout = QVBoxLayout(root)

        header = QHBoxLayout()
        header.addWidget(QLabel("SERIAL PORT"))
        self.port = QLineEdit(self.transport.port)
        header.addWidget(self.port, 1)
        header.addWidget(QLabel("BAUD"))
        self.baud = QComboBox()
        self.baud.addItems(["57600"])
        header.addWidget(self.baud)
        self.connect_button = QPushButton("CONNECT")
        self.connect_button.clicked.connect(self.toggle_connection)
        header.addWidget(self.connect_button)
        layout.addLayout(header)

        controls = QHBoxLayout()
        self.start1 = QPushButton("START CH1")
        self.stop1 = QPushButton("STOP CH1")
        self.start2 = QPushButton("START CH2")
        self.stop2 = QPushButton("STOP CH2")
        self.start_all = QPushButton("START ALL")
        self.stop_all = QPushButton("STOP ALL")
        self.start1.clicked.connect(lambda: self.start_channel(1))
        self.stop1.clicked.connect(lambda: self.stop_channel(1))
        self.start2.clicked.connect(lambda: self.start_channel(2))
        self.stop2.clicked.connect(lambda: self.stop_channel(2))
        self.start_all.clicked.connect(lambda: self.start_channel(None))
        self.stop_all.clicked.connect(lambda: self.stop_channel(None))
        for button in (self.start1, self.stop1, self.start2, self.stop2, self.start_all, self.stop_all):
            controls.addWidget(button)
        layout.addLayout(controls)

        target = QHBoxLayout()
        target.addWidget(QLabel("5A TARGET"))
        target_value = QLabel(f"{self.TARGET_CURRENT:.2f} A")
        target_value.setStyleSheet("font-size:18px;font-weight:bold;")
        target.addWidget(target_value)
        target.addStretch()
        self.connection_state = QLabel("DISCONNECTED")
        target.addWidget(self.connection_state)
        layout.addLayout(target)

        grid = QGridLayout()
        grid.addWidget(self.cards[1], 0, 0)
        grid.addWidget(self.cards[2], 0, 1)
        layout.addLayout(grid)

        result = QGroupBox("EVALUATION STATUS")
        result_layout = QGridLayout(result)
        self.result_values = {}
        for row, key in enumerate(("CH1", "CH2", "SYSTEM")):
            result_layout.addWidget(QLabel(key), row, 0)
            value = QLabel("READY")
            value.setStyleSheet("font-size:15px;font-weight:bold;")
            result_layout.addWidget(value, row, 1)
            self.result_values[key] = value
        layout.addWidget(result)

        debug = QGroupBox("DEBUG / DIAGNOSTIC (NOT MEASUREMENT DATA)")
        debug_layout = QVBoxLayout(debug)
        self.debug_log = QPlainTextEdit()
        self.debug_log.setReadOnly(True)
        self.debug_log.setMaximumBlockCount(300)
        debug_layout.addWidget(self.debug_log)
        layout.addWidget(debug)

        self.setCentralWidget(root)
        self._set_controls_enabled(False)

    def toggle_connection(self):
        if self.transport.connected:
            self.transport.disconnect()
            self.timer.stop()
            self.connection_state.setText("DISCONNECTED")
            self.connect_button.setText("CONNECT")
            self._set_controls_enabled(False)
            self._set_all_state("READY")
            return
        self.transport.port = self.port.text().strip() or "/dev/ttyACM0"
        self.transport.baudrate = int(self.baud.currentText())
        if not self.transport.connect():
            QMessageBox.warning(self, "Serial", f"接続できませんでした。\n{self.transport.last_error}")
            return
        self.connection_state.setText(f"CONNECTED / {self.transport.port}")
        self.connect_button.setText("DISCONNECT")
        self._set_controls_enabled(True)
        self.timer.start()

    def _set_controls_enabled(self, enabled):
        for button in (self.start1, self.stop1, self.start2, self.stop2, self.start_all, self.stop_all):
            button.setEnabled(enabled)

    def _set_all_state(self, state):
        for card in self.cards.values():
            card.set_state(state)
        for key in self.result_values:
            self.result_values[key].setText(state)

    def start_channel(self, channel):
        if not self.transport.connected:
            return
        self.transport.start(channel)
        if channel is None:
            self._set_all_state("RUN")
        else:
            self.cards[channel].set_state("RUN")
            self.result_values[f"CH{channel}"].setText("RUN")
        self.result_values["SYSTEM"].setText("RUN")

    def stop_channel(self, channel):
        if not self.transport.connected:
            return
        self.transport.stop(channel)
        if channel is None:
            self._set_all_state("STOP")
        else:
            self.cards[channel].set_state("STOP")
            self.result_values[f"CH{channel}"].setText("STOP")

    def poll_serial(self):
        for line in self.transport.read_lines():
            if line.startswith("DEBUG") or line.startswith("INA3221"):
                self.debug_log.appendPlainText(line)
                continue
            sample = self.transport.parse_data(line)
            if sample is None:
                self.debug_log.appendPlainText(line)
                continue
            if sample.channel in self.cards:
                self.cards[sample.channel].set_sample(sample, self.TARGET_CURRENT)
                state = sample.state if sample.state and sample.state != "--" else "RUN"
                self.result_values[f"CH{sample.channel}"].setText(state)
                if state in ("COMPLETE", "TIMEOUT", "STOP"):
                    self.cards[sample.channel].set_state(state)
            # Raw DATA is never routed to the DEBUG panel.

    def closeEvent(self, event):
        self.timer.stop()
        self.transport.disconnect()
        event.accept()
