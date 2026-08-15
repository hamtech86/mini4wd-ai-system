from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QPushButton, QLabel, QComboBox

from controllers.recipe import (
    BreakinRecipe,
    BreakinPhase,
    default_speed_recipe,
    default_torque_recipe,
)
from ui.result_formatter import format_analysis_result


class BreakinWorker(QThread):
    """Run the blocking BreakinController outside the Qt GUI thread."""
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, controller, recipe, instance_id):
        super().__init__()
        self.controller = controller
        self.recipe = recipe
        self.instance_id = instance_id

    def run(self):
        try:
            result = self.controller.start(self.recipe, instance_id=self.instance_id)
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    """MOTOR_BREAKIN_V3 production break-in UI."""

    def __init__(self, context=None):
        super().__init__()
        self.context = context
        self.breakin_worker = None

        if isinstance(context, dict):
            self.breakin_controller = context.get("breakin_controller")
        else:
            self.breakin_controller = getattr(context, "breakin_controller", None)

        self.setWindowTitle("MINI4WD AI SYSTEM - Motor Break-in")
        self.resize(700, 520)

        root = QWidget()
        layout = QVBoxLayout()
        self.status = QLabel("READY")
        self.result_display = QLabel("RESULT: --")
        self.result_display.setWordWrap(True)
        self.instance_selector = QComboBox()
        self._load_motor_instances()
        self.recipe_selector = QComboBox()
        self.recipe_selector.addItem("TORQUE - automatic Torque Tune recipe", "TORQUE")
        self.recipe_selector.addItem("SPEED - 360 sec", "SPEED")
        self.recipe_selector.addItem("TEST - 3 sec / PWM 80", "TEST")
        self.start_button = QPushButton("START BREAK-IN")
        self.stop_button = QPushButton("EMERGENCY STOP")

        self.start_button.clicked.connect(self.start_breakin)
        self.stop_button.clicked.connect(self.stop_breakin)

        layout.addWidget(self.status)
        layout.addWidget(QLabel("ANALYSIS / BENCHMARK"))
        layout.addWidget(self.result_display)
        layout.addWidget(QLabel("MOTOR INSTANCE"))
        layout.addWidget(self.instance_selector)
        layout.addWidget(QLabel("RECIPE"))
        layout.addWidget(self.recipe_selector)
        layout.addWidget(self.start_button)
        layout.addWidget(self.stop_button)
        root.setLayout(layout)
        self.setCentralWidget(root)

    def _load_motor_instances(self):
        self.instance_selector.clear()
        database = getattr(self.breakin_controller, "database", None)
        if database is None:
            self.instance_selector.addItem("ERROR: DATABASE NOT AVAILABLE", None)
            return

        rows = database.execute(
            """
            SELECT instance_id, serial_number, nickname, status
            FROM motor_instance
            WHERE is_deleted=0
            ORDER BY instance_id
            """
        ).fetchall()

        for row in rows:
            serial = row[1] or ""
            nickname = row[2] or ""
            label = f"#{row[0]} {serial} {nickname}".strip()
            self.instance_selector.addItem(label, int(row[0]))

        if self.instance_selector.count() == 0:
            self.instance_selector.addItem("NO MOTOR INSTANCE", None)

    def selected_recipe(self):
        recipe_type = self.recipe_selector.currentData()
        if recipe_type == "TEST":
            return BreakinRecipe(
                name="TEST",
                phases=[BreakinPhase(name="TEST", duration_sec=3, pwm=80, direction="FWD")],
            )
        if recipe_type == "TORQUE":
            return default_torque_recipe()
        return default_speed_recipe()

    def start_breakin(self):
        if not self.breakin_controller:
            self.status.setText("ERROR: CONTROLLER NOT AVAILABLE")
            return None
        if self.breakin_worker and self.breakin_worker.isRunning():
            return None

        instance_id = self.instance_selector.currentData()
        if instance_id is None:
            self.status.setText("ERROR: MOTOR INSTANCE NOT SELECTED")
            return None

        self.status.setText(f"BREAK-IN RUNNING / INSTANCE #{instance_id}")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        recipe = self.selected_recipe()
        self.breakin_worker = BreakinWorker(
            self.breakin_controller,
            recipe,
            instance_id,
        )
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
        self.result_display.setText(format_analysis_result(result))
