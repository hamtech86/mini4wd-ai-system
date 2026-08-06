from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel


class MainWindow(QMainWindow):
    """Temporary UI for MOTOR_BREAKIN_V3 integration testing."""

    def __init__(self, context=None):
        super().__init__()
        self.context = context
        self.breakin_controller = getattr(context, "breakin_controller", None)

        self.setWindowTitle("MINI4WD AI SYSTEM - Motor Break-in")
        self.resize(600, 400)

        root = QWidget()
        layout = QVBoxLayout()

        self.status = QLabel("READY")
        self.start_button = QPushButton("START BREAK-IN")
        self.stop_button = QPushButton("EMERGENCY STOP")

        self.start_button.clicked.connect(self.start_breakin)
        self.stop_button.clicked.connect(self.stop_breakin)

        layout.addWidget(self.status)
        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)

        root.setLayout(layout)
        self.setCentralWidget(root)

    def start_breakin(self):
        self.status.setText("BREAK-IN RUNNING")
        if self.breakin_controller:
            self.breakin_controller.start()

    def stop_breakin(self):
        self.status.setText("STOPPED")
        if self.breakin_controller:
            self.breakin_controller.emergency_stop()
