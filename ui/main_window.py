from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel

from controllers.recipe import default_speed_recipe


class MainWindow(QMainWindow):
    """Temporary UI for MOTOR_BREAKIN_V3 integration testing."""

    def __init__(self, context=None):
        super().__init__()
        self.context = context

        if isinstance(context, dict):
            self.breakin_controller = context.get("breakin_controller")
        else:
            self.breakin_controller = getattr(
                context,
                "breakin_controller",
                None,
            )

        self.setWindowTitle("MINI4WD AI SYSTEM - Motor Break-in")
        self.resize(600, 400)

        root = QWidget()
        layout = QVBoxLayout()

        self.status = QLabel("READY")
        self.result_display = QLabel("RESULT: --")
        self.start_button = QPushButton("START BREAK-IN")
        self.stop_button = QPushButton("EMERGENCY STOP")

        self.start_button.clicked.connect(self.start_breakin)
        self.stop_button.clicked.connect(self.stop_breakin)

        layout.addWidget(self.status)
        layout.addWidget(self.result_display)
        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)

        root.setLayout(layout)
        self.setCentralWidget(root)

    def start_breakin(self):
        if not self.breakin_controller:
            self.status.setText("ERROR: CONTROLLER NOT AVAILABLE")
            return None

        self.status.setText("BREAK-IN RUNNING")
        recipe = default_speed_recipe()

        try:
            result = self.breakin_controller.start(recipe)
            self.display_analysis_result(result)
            self.status.setText("BREAK-IN COMPLETE")
            return result
        except Exception as exc:
            self.status.setText(f"ERROR: {exc}")
            raise

    def stop_breakin(self):
        self.status.setText("STOPPED")
        if self.breakin_controller:
            self.breakin_controller.emergency_stop()

    def display_analysis_result(self, result):
        """Display the AnalysisResult returned by BreakinController."""
        if result is None:
            self.result_display.setText("RESULT: --")
            return

        if isinstance(result, list):
            self.result_display.setText(f"RESULT: {len(result)} ANALYSIS RESULT(S)")
            return

        if isinstance(result, dict):
            summary = result.get("summary") or result.get("result") or result.get("score")
            if summary is not None:
                self.result_display.setText(f"RESULT: {summary}")
                return

        self.result_display.setText(f"RESULT: {result}")
