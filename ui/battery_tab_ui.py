"""Integrated Battery UI shell.

Keeps Battery operation separate from the Motor Break-in UI while preserving
manual Instance/Result registration and the existing 5A device contract.
"""
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton, QComboBox, QTabWidget
from ui.battery_database_ui import BatteryDatabaseDialog

class BatteryTab(QWidget):
    def __init__(self, db_path, parent=None):
        super().__init__(parent)
        self.db_path = str(db_path)
        self._build()

    def _build(self):
        root = QVBoxLayout(self)
        connection = QGroupBox("BATTERY DEVICE CONNECTION")
        row = QHBoxLayout(connection)
        self.status = QLabel("BATTERY: DISCONNECTED  /dev/ttyUSB0")
        self.connect_button = QPushButton("BATTERY CONNECT")
        self.disconnect_button = QPushButton("BATTERY DISCONNECT")
        self.disconnect_button.setEnabled(False)
        row.addWidget(self.status); row.addWidget(self.connect_button); row.addWidget(self.disconnect_button)
        root.addWidget(connection)

        tabs = QTabWidget()
        operation = QWidget(); op = QVBoxLayout(operation)
        instances = QGroupBox("BATTERY INSTANCE ASSIGNMENT")
        ir = QHBoxLayout(instances)
        self.ch1_instance = QComboBox(); self.ch1_instance.setEditable(False)
        self.ch2_instance = QComboBox(); self.ch2_instance.setEditable(False)
        ir.addWidget(QLabel("CH1")); ir.addWidget(self.ch1_instance); ir.addWidget(QLabel("CH2")); ir.addWidget(self.ch2_instance)
        op.addWidget(instances)

        controls = QGroupBox("5A DISCHARGE")
        cr = QHBoxLayout(controls)
        self.ch1_start = QPushButton("CH1 START"); self.ch1_stop = QPushButton("CH1 STOP")
        self.ch2_start = QPushButton("CH2 START"); self.ch2_stop = QPushButton("CH2 STOP")
        self.all_start = QPushButton("ALL START"); self.all_stop = QPushButton("ALL STOP")
        for w in (self.ch1_start,self.ch1_stop,self.ch2_start,self.ch2_stop,self.all_start,self.all_stop): cr.addWidget(w)
        op.addWidget(controls)

        live = QGroupBox("LIVE DATA")
        lr = QHBoxLayout(live)
        self.live_labels = {}
        for name in ("CH1 Voltage", "CH1 Current", "CH1 PWM", "CH1 Time", "CH2 Voltage", "CH2 Current", "CH2 PWM", "CH2 Time"):
            label = QLabel(f"{name}: --"); self.live_labels[name] = label; lr.addWidget(label)
        op.addWidget(live)
        op.addWidget(QLabel("Result is retained as measurement data and confirmed manually before database registration."))
        tabs.addTab(operation, "5A DISCHARGE")

        db_page = QWidget(); db_layout = QVBoxLayout(db_page)
        db_button = QPushButton("OPEN BATTERY INSTANCE / RESULT DATABASE")
        db_button.clicked.connect(self.open_database)
        db_layout.addWidget(db_button); db_layout.addStretch(1)
        tabs.addTab(db_page, "DATABASE")
        root.addWidget(tabs)

    def open_database(self):
        dialog = BatteryDatabaseDialog(self.db_path, self)
        dialog.exec_()
