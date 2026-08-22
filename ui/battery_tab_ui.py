"""Integrated Battery operation tab.

The top-level window owns the BatterySerial connection. This tab only exposes
verified 5A commands, live DATA frames, Instance assignment and database UI.
"""
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel, QPushButton, QComboBox, QTabWidget, QMessageBox
from battery_system.serial import BatterySerial
from ui.battery_database_ui import BatteryDatabaseDialog

class BatteryTab(QWidget):
    def __init__(self, db_path, transport=None, parent=None):
        super().__init__(parent)
        self.db_path = str(db_path)
        self.transport = transport or BatterySerial()
        self._build()
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.poll_serial)
        self._set_controls_enabled(False)

    def _build(self):
        root = QVBoxLayout(self)
        tabs = QTabWidget()
        operation = QWidget(); op = QVBoxLayout(operation)

        instances = QGroupBox("BATTERY INSTANCE ASSIGNMENT")
        ir = QHBoxLayout(instances)
        self.ch1_instance = QComboBox(); self.ch1_instance.setEditable(False)
        self.ch2_instance = QComboBox(); self.ch2_instance.setEditable(False)
        self.ch1_instance.currentIndexChanged.connect(self._validate_instance_assignment)
        self.ch2_instance.currentIndexChanged.connect(self._validate_instance_assignment)
        ir.addWidget(QLabel("CH1")); ir.addWidget(self.ch1_instance)
        ir.addWidget(QLabel("CH2")); ir.addWidget(self.ch2_instance)
        op.addWidget(instances)

        controls = QGroupBox("5A DISCHARGE")
        cr = QGridLayout(controls)
        self.ch1_start = QPushButton("CH1 START"); self.ch1_stop = QPushButton("CH1 STOP")
        self.ch2_start = QPushButton("CH2 START"); self.ch2_stop = QPushButton("CH2 STOP")
        self.all_start = QPushButton("ALL START"); self.all_stop = QPushButton("ALL STOP")
        self.ch1_start.clicked.connect(lambda: self.start_channel(1))
        self.ch1_stop.clicked.connect(lambda: self.stop_channel(1))
        self.ch2_start.clicked.connect(lambda: self.start_channel(2))
        self.ch2_stop.clicked.connect(lambda: self.stop_channel(2))
        self.all_start.clicked.connect(lambda: self.start_channel(None))
        self.all_stop.clicked.connect(lambda: self.stop_channel(None))
        buttons = (self.ch1_start, self.ch1_stop, self.ch2_start, self.ch2_stop, self.all_start, self.all_stop)
        for i, button in enumerate(buttons): cr.addWidget(button, i // 3, i % 3)
        op.addWidget(controls)

        live = QGroupBox("LIVE DATA")
        grid = QGridLayout(live)
        self.live_labels = {}
        fields = (("CH1", "Voltage"), ("CH1", "Current"), ("CH1", "PWM"), ("CH1", "Time"),
                  ("CH2", "Voltage"), ("CH2", "Current"), ("CH2", "PWM"), ("CH2", "Time"))
        for i, (channel, field) in enumerate(fields):
            label = QLabel(f"{channel} {field}: --")
            self.live_labels[(channel, field)] = label
            grid.addWidget(label, i // 4, i % 4)
        op.addWidget(live)
        op.addWidget(QLabel("Measurement data is kept as the source record. Result registration remains manual."))
        tabs.addTab(operation, "5A DISCHARGE")

        db_page = QWidget(); db_layout = QVBoxLayout(db_page)
        db_button = QPushButton("OPEN BATTERY INSTANCE / RESULT DATABASE")
        db_button.clicked.connect(self.open_database)
        db_layout.addWidget(db_button); db_layout.addStretch(1)
        tabs.addTab(db_page, "DATABASE")
        root.addWidget(tabs)

    def set_connected(self, connected):
        self._set_controls_enabled(connected)
        if connected:
            self.timer.start()
        else:
            self.timer.stop()

    def _set_controls_enabled(self, enabled):
        for button in (self.ch1_start, self.ch1_stop, self.ch2_start, self.ch2_stop, self.all_start, self.all_stop):
            button.setEnabled(enabled)

    def _validate_instance_assignment(self):
        a = self.ch1_instance.currentData()
        b = self.ch2_instance.currentData()
        if a is not None and b is not None and a == b:
            sender = self.sender()
            previous = sender.property("previous_index") if sender is not None else None
            if previous is not None:
                sender.blockSignals(True); sender.setCurrentIndex(int(previous)); sender.blockSignals(False)
            QMessageBox.warning(self, "Battery Instance", "同じ測定でCH1とCH2に同じBattery Instanceは指定できません。")
            return False
        for combo in (self.ch1_instance, self.ch2_instance):
            combo.setProperty("previous_index", combo.currentIndex())
        return True

    def start_channel(self, channel):
        if not self.transport.connected:
            return
        if not self._validate_instance_assignment():
            return
        if not self.transport.start(channel):
            QMessageBox.warning(self, "Battery", "STARTコマンドを送信できませんでした。")

    def stop_channel(self, channel):
        if not self.transport.connected:
            return
        if not self.transport.stop(channel):
            QMessageBox.warning(self, "Battery", "STOPコマンドを送信できませんでした。")

    def poll_serial(self):
        for line in self.transport.read_lines():
            sample = self.transport.parse_data(line)
            if sample is None:
                continue
            prefix = f"CH{sample.channel}"
            self.live_labels[(prefix, "Voltage")].setText(f"{prefix} Voltage: {sample.voltage:.3f} V")
            self.live_labels[(prefix, "Current")].setText(f"{prefix} Current: {sample.current:.3f} A")
            self.live_labels[(prefix, "PWM")].setText(f"{prefix} PWM: {sample.pwm}")
            self.live_labels[(prefix, "Time")].setText(f"{prefix} Time: {sample.elapsed_sec:.1f} s")

    def open_database(self):
        dialog = BatteryDatabaseDialog(self.db_path, self)
        dialog.exec_()
