from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel, QComboBox

from controllers.recipe import BreakinRecipe, BreakinPhase, default_speed_recipe


class BreakinWorker(QThread):
    """Run the blocking BreakinController outside the Qt GUI thread."""
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, controller, recipe):
        super().__init__()
        self.controller = controller
        self.recipe = recipe

    def run(self):
        try:
            result = self.controller.start(self.recipe)
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    """Temporary UI for MOTOR_BREAKIN_V3 integration testing."""

    def __init__(self, context=None):
        super().__init__()
        self.context = context
        self.breakin_worker = None

        if isinstance(context, dict):
            self.breakin_controller = context.get("breakin_controller")
        else:
            self.breakin_controller = getattr(context, "breakin_controller", None)

        self.setWindowTitle("MINI4WD AI SYSTEM - Motor Break-in")
        self.resize(600, 400)

        root = QWidget()
        layout = QVBoxLayout()
        self.status = QLabel("READY")
        self.result_display = QLabel("RESULT: --")
        self.recipe_selector = QComboBox()
        self.recipe_selector.addItem("TEST - 3 sec / PWM 80", "TEST")
        self.recipe_selector.addItem("SPEED - 360 sec", "SPEED")
        self.start_button = QPushButton("START BREAK-IN")
        self.stop_button = QPushButton("EMERGENCY STOP")

        self.start_button.clicked.connect(self.start_breakin)
        self.stop_button.clicked.connect(self.stop_breakin)

        layout.addWidget(self.status)
        layout.addWidget(self.result_display)
        layout.addWidget(QLabel("RECIPE"))
        layout.addWidget(self.recipe_selector)
        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)
        root.setLayout(layout)
        self.setCentralWidget(root)

    def selected_recipe(self):
        if self.recipe_selector.currentData() == "TEST":
            return BreakinRecipe(
                name="TEST",
                phases=[BreakinPhase(name="TEST", duration_sec=3, pwm=80, direction="FWD")],
            )
        return default_speed_recipe()

    def start_breakin(self):
        if not self.breakin_controller:
            self.status.setText("ERROR: CONTROLLER NOT AVAILABLE")
            return None
        if self.breakin_worker and self.breakin_worker.isRunning():
            return None
        self.status.setText("BREAK-IN RUNNING")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        recipe = self.selected_recipe()
        self.breakin_worker = BreakinWorker(self.breakin_controller, recipe)
        self.breakin_worker.completed.connect(self.on_breakin_complete)
        self.breakin_worker.failed.connect(self.on_breakin_failed)
        self.breakin_worker.finished.connect(self.on_worker_finished)
        self.breakin_worker.start()
        return None

    def stop_breakin(self):
        if not self.breakin_controller:
            self.status.setText("ERROR: CONTROLLER NOT AVAILABLE")
            return
        self.breakin_controller.emergency_stop()
        self.status.setText("STOPPED")
        self.start_button.setEnabled(True)

    def on_breakin_complete(self, result):
        self.display_analysis_result(result)
        self.status.setText("BREAK-IN COMPLETE")

    def on_breakin_failed(self, message):
        self.status.setText(f"ERROR: {message}")

    def on_worker_finished(self):
        self.start_button.setEnabled(True)
        self.breakin_worker = None

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
