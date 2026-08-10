"""MOTOR_BREAKIN_V3 main window.

Operator UI for the motor break-in system. Recipe definition and execution
remain in RecipeEngine/BreakinController; the UI selects and starts a
validated recipe or a standalone 3 V benchmark test.
"""

from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from controllers.recipe_engine import RecipeEngine


class BreakinWorker(QThread):
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, controller, recipe=None, benchmark=False):
        super().__init__()
        self.controller = controller
        self.recipe = recipe
        self.benchmark = benchmark

    def run(self):
        try:
            if self.benchmark:
                result = self.controller.benchmark_3v(duration_sec=10)
            else:
                result = self.controller.start(self.recipe)
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    """Integrated operator UI for MOTOR_BREAKIN_V3."""

    BENCHMARK_KEY = "__MOTOR_BENCHMARK_TEST__"

    def __init__(self, context=None):
        super().__init__()
        self.context = context
        self.breakin_worker = None
        self.recipe_engine = RecipeEngine(
            str(Path(__file__).resolve().parent.parent / "config" / "breakin_recipes.yaml")
        )

        if isinstance(context, dict):
            self.breakin_controller = context.get("breakin_controller")
        else:
            self.breakin_controller = getattr(context, "breakin_controller", None)

        self.setWindowTitle("MINI4WD AI SYSTEM - MOTOR BREAKIN V3")
        self.resize(900, 620)
        self._build_ui()
        self._load_recipes()
        self._set_ready_state()

    def _build_ui(self):
        root = QWidget()
        main = QVBoxLayout(root)

        title = QLabel("MOTOR BREAK-IN SYSTEM")
        title.setStyleSheet("font-size: 22px; font-weight: bold;")
        main.addWidget(title)

        self.status = QLabel("READY")
        self.status.setStyleSheet("font-size: 16px; font-weight: bold;")
        main.addWidget(self.status)

        content = QHBoxLayout()

        recipe_box = QGroupBox("BREAK-IN / BENCHMARK")
        recipe_layout = QVBoxLayout(recipe_box)
        self.recipe_selector = QComboBox()
        self.recipe_selector.currentIndexChanged.connect(self._recipe_changed)
        recipe_layout.addWidget(self.recipe_selector)

        self.description = QLabel("-")
        self.description.setWordWrap(True)
        recipe_layout.addWidget(self.description)

        self.phase_list = QListWidget()
        recipe_layout.addWidget(self.phase_list)
        content.addWidget(recipe_box, 2)

        info_box = QGroupBox("RECIPE / BENCHMARK")
        info_layout = QFormLayout(info_box)
        self.brush_value = QLabel("-")
        self.objective_value = QLabel("-")
        self.target_rpm_value = QLabel("-")
        self.torque_priority_value = QLabel("-")
        self.benchmark_value = QLabel("-")
        self.safety_value = QLabel("-")
        info_layout.addRow("Brush", self.brush_value)
        info_layout.addRow("Objective", self.objective_value)
        info_layout.addRow("Target RPM", self.target_rpm_value)
        info_layout.addRow("Torque Priority", self.torque_priority_value)
        info_layout.addRow("Benchmark", self.benchmark_value)
        info_layout.addRow("Safety", self.safety_value)
        content.addWidget(info_box, 1)
        main.addLayout(content)

        result_box = QGroupBox("RESULT")
        result_layout = QFormLayout(result_box)
        self.result_display = QLabel("--")
        self.rpm_display = QLabel("--")
        self.torque_display = QLabel("--")
        self.lifecycle_display = QLabel("--")
        self.weight_display = QLabel("--")
        result_layout.addRow("Summary", self.result_display)
        result_layout.addRow("Estimated RPM", self.rpm_display)
        result_layout.addRow("Estimated Torque", self.torque_display)
        result_layout.addRow("Brush Lifecycle", self.lifecycle_display)
        result_layout.addRow("Estimated Compatible Weight", self.weight_display)
        main.addWidget(result_box)

        controls = QHBoxLayout()
        self.start_button = QPushButton("START BREAK-IN")
        self.stop_button = QPushButton("EMERGENCY STOP")
        self.stop_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_breakin)
        self.stop_button.clicked.connect(self.stop_breakin)
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        main.addLayout(controls)

        self.setCentralWidget(root)

    def _load_recipes(self):
        self.recipe_selector.clear()
        for name in self.recipe_engine.names():
            self.recipe_selector.addItem(name, name)
        self.recipe_selector.addItem("MOTOR BENCHMARK TEST (3V / 10s)", self.BENCHMARK_KEY)

    def _set_ready_state(self):
        if self.breakin_controller:
            self.status.setText("READY / CONTROLLER CONNECTED")
        else:
            self.status.setText("ERROR / CONTROLLER NOT AVAILABLE")
        if self.recipe_selector.count():
            self._recipe_changed(0)

    def _recipe_changed(self, _index):
        name = self.recipe_selector.currentData()
        if name == self.BENCHMARK_KEY:
            self.description.setText(
                "Standalone 3 V motor benchmark. No break-in stages are executed. "
                "The test holds approximately 3.00 V using closed-loop PWM control for 10 seconds."
            )
            self.brush_value.setText("UNKNOWN")
            self.objective_value.setText("MEASUREMENT")
            self.target_rpm_value.setText("--")
            self.torque_priority_value.setText("0.50")
            self.benchmark_value.setText("3.00 V / 10 s")
            safety = self.recipe_engine.safety()
            self.safety_value.setText(
                f"{safety.get('max_current', 5.0):g} A / "
                f"{safety.get('max_motor_temperature', 70.0):g} °C"
            )
            self.phase_list.clear()
            self.phase_list.addItem("BENCHMARK_3V_TEST: closed-loop 3.00 V / 10s")
            return

        recipe = self.selected_recipe()
        if recipe is None:
            return
        self.description.setText(recipe.description or "-")
        self.brush_value.setText(recipe.brush)
        self.objective_value.setText(recipe.objective)
        self.target_rpm_value.setText(
            "--" if recipe.target_rpm is None else f"{recipe.target_rpm:,} rpm"
        )
        self.torque_priority_value.setText(f"{recipe.torque_priority:.2f}")
        benchmark = self.recipe_engine.benchmark()
        self.benchmark_value.setText(
            f"{benchmark.get('target_voltage', 3.00):.2f} V / "
            f"{benchmark.get('duration_sec', 120)} s"
        )
        safety = self.recipe_engine.safety()
        self.safety_value.setText(
            f"{safety.get('max_current', 5.0):g} A / "
            f"{safety.get('max_motor_temperature', 70.0):g} °C"
        )
        self.phase_list.clear()
        for phase in recipe.phases:
            control = f", {phase.control}" if phase.control else ""
            self.phase_list.addItem(
                f"{phase.name}: PWM {phase.pwm}, {phase.duration_sec}s{control}"
            )

    def selected_recipe(self):
        name = self.recipe_selector.currentData()
        if not name or name == self.BENCHMARK_KEY:
            return None
        return self.recipe_engine.get(name)

    def start_breakin(self):
        if not self.breakin_controller:
            QMessageBox.warning(self, "Controller", "BreakinController is not available.")
            return
        if self.breakin_worker and self.breakin_worker.isRunning():
            return

        is_benchmark = self.recipe_selector.currentData() == self.BENCHMARK_KEY
        recipe = None if is_benchmark else self.selected_recipe()
        if not is_benchmark and recipe is None:
            QMessageBox.warning(self, "Recipe", "No valid recipe is selected.")
            return

        label = "MOTOR BENCHMARK TEST" if is_benchmark else f"BREAK-IN / {recipe.name}"
        self.status.setText(f"RUNNING / {label}")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.recipe_selector.setEnabled(False)
        self.result_display.setText("RUNNING...")
        self.rpm_display.setText("--")
        self.torque_display.setText("--")
        self.lifecycle_display.setText("--")
        self.weight_display.setText("--")
        self.breakin_worker = BreakinWorker(
            self.breakin_controller, recipe=recipe, benchmark=is_benchmark
        )
        self.breakin_worker.completed.connect(self.on_breakin_complete)
        self.breakin_worker.failed.connect(self.on_breakin_failed)
        self.breakin_worker.finished.connect(self.on_worker_finished)
        self.breakin_worker.start()

    def stop_breakin(self):
        if self.breakin_controller:
            self.breakin_controller.emergency_stop()
        self.status.setText("STOPPED / EMERGENCY STOP")
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.recipe_selector.setEnabled(True)

    def on_breakin_complete(self, result):
        self.display_analysis_result(result)
        is_benchmark = self.recipe_selector.currentData() == self.BENCHMARK_KEY
        self.status.setText(
            "MOTOR BENCHMARK COMPLETE" if is_benchmark else "BREAK-IN COMPLETE / BENCHMARK FINISHED"
        )

    def on_breakin_failed(self, message):
        self.status.setText(f"ERROR / {message}")
        self.result_display.setText("ERROR")
        self.stop_button.setEnabled(False)

    def on_worker_finished(self):
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.recipe_selector.setEnabled(True)
        self.breakin_worker = None

    def display_analysis_result(self, result):
        if result is None:
            self.result_display.setText("NO RESULT")
            return
        if isinstance(result, list):
            self.result_display.setText(f"{len(result)} measurement(s) collected")
            self._display_latest_measurement(result)
            return
        if isinstance(result, dict):
            summary = result.get("summary") or result.get("result") or result.get("score")
            self.result_display.setText(str(summary) if summary is not None else "COMPLETE")
            self.rpm_display.setText(str(result.get("estimated_rpm", result.get("rpm", "--"))))
            self.torque_display.setText(str(result.get("estimated_torque", result.get("torque", "--"))))
            self.lifecycle_display.setText(str(result.get("brush_lifecycle", result.get("lifecycle", "--"))))
            self.weight_display.setText(str(result.get("estimated_weight", result.get("compatible_weight", "--"))))
            return
        self.result_display.setText(str(result))

    def _display_latest_measurement(self, results):
        if not results:
            return
        latest = results[-1]
        if not isinstance(latest, dict):
            return
        self.rpm_display.setText(str(latest.get("rpm", "--")))
        self.torque_display.setText(str(latest.get("torque", "--")))
        self.lifecycle_display.setText("-- (benchmark only)")
        self.weight_display.setText("-- (benchmark only)")
