"""MOTOR_BREAKIN_V3 main window.

Operator UI for the motor break-in system. Recipe definition and execution
remain in RecipeEngine/BreakinController; the UI selects and starts a
validated recipe or a standalone 3 V benchmark test.
"""

from pathlib import Path

from PyQt5.QtCore import QThread, pyqtSignal
from PyQt5.QtWidgets import (
    QApplication,
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

from analysis.vehicle_weight import estimate_vehicle_weight
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

    BENCHMARK_VEHICLE_WEIGHT_G = 130.0
    BENCHMARK_TIRE_DIAMETER_MM = 24.0
    BENCHMARK_GEAR_RATIO = 3.5

    MOTOR_TYPES = (
        ("ATOMIC TUNE 25K", "ATOMIC_25K"),
        ("TORQUE TUNE 23K", "TORQUE_TUNE_23K"),
        ("TUNE SERIES / OPTIMIZED", "TUNE_OPTIMIZED"),
        ("DASH SERIES / OPTIMIZED", "DASH_OPTIMIZED"),
        ("CUSTOM / BENCHMARK ONLY", BENCHMARK_KEY),
    )

    def __init__(self, context=None):
        super().__init__()
        self.context = context
        self.breakin_worker = None
        self.last_benchmark_report = ""
        self.last_benchmark_results = None
        self.recipe_engine = RecipeEngine(
            str(Path(__file__).resolve().parent.parent / "config" / "breakin_recipes.yaml")
        )

        if isinstance(context, dict):
            self.breakin_controller = context.get("breakin_controller")
        else:
            self.breakin_controller = getattr(context, "breakin_controller", None)

        self.setWindowTitle("MINI4WD AI SYSTEM - MOTOR BREAKIN V3")
        self.resize(900, 700)
        self._build_ui()
        self._load_recipes()
        self._load_motor_types()
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

        recipe_box = QGroupBox("MOTOR / BREAK-IN / BENCHMARK")
        recipe_layout = QVBoxLayout(recipe_box)

        self.motor_type_selector = QComboBox()
        self.motor_type_selector.currentIndexChanged.connect(self._motor_type_changed)
        recipe_layout.addWidget(self.motor_type_selector)

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
        self.motor_type_value = QLabel("-")
        self.brush_value = QLabel("-")
        self.objective_value = QLabel("-")
        self.target_rpm_value = QLabel("-")
        self.torque_priority_value = QLabel("-")
        self.benchmark_value = QLabel("-")
        self.safety_value = QLabel("-")
        self.vehicle_weight_value = QLabel("-")
        self.tire_value = QLabel("-")
        self.gear_ratio_value = QLabel("-")
        info_layout.addRow("Motor Type", self.motor_type_value)
        info_layout.addRow("Brush", self.brush_value)
        info_layout.addRow("Objective", self.objective_value)
        info_layout.addRow("Target RPM", self.target_rpm_value)
        info_layout.addRow("Torque Priority", self.torque_priority_value)
        info_layout.addRow("Benchmark", self.benchmark_value)
        info_layout.addRow("Vehicle Weight", self.vehicle_weight_value)
        info_layout.addRow("Tire Diameter", self.tire_value)
        info_layout.addRow("Gear Ratio", self.gear_ratio_value)
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
        self.benchmark_detail_display = QLabel("--")
        self.benchmark_detail_display.setWordWrap(True)
        result_layout.addRow("Summary", self.result_display)
        result_layout.addRow("Estimated RPM", self.rpm_display)
        result_layout.addRow("Estimated Torque", self.torque_display)
        result_layout.addRow("Compatible Weight", self.weight_display)
        result_layout.addRow("Brush Lifecycle", self.lifecycle_display)
        result_layout.addRow("Benchmark Detail", self.benchmark_detail_display)
        main.addWidget(result_box)

        controls = QHBoxLayout()
        self.start_button = QPushButton("START BREAK-IN")
        self.stop_button = QPushButton("EMERGENCY STOP")
        self.copy_benchmark_button = QPushButton("COPY BENCHMARK RESULT")
        self.stop_button.setEnabled(False)
        self.copy_benchmark_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_breakin)
        self.stop_button.clicked.connect(self.stop_breakin)
        self.copy_benchmark_button.clicked.connect(self.copy_benchmark_result)
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.copy_benchmark_button)
        main.addLayout(controls)

        self.setCentralWidget(root)

    def _load_recipes(self):
        self.recipe_selector.clear()
        for name in self.recipe_engine.names():
            self.recipe_selector.addItem(name, name)
        self.recipe_selector.addItem("MOTOR BENCHMARK TEST (3V / 10s)", self.BENCHMARK_KEY)

    def _load_motor_types(self):
        self.motor_type_selector.clear()
        for label, key in self.MOTOR_TYPES:
            self.motor_type_selector.addItem(label, key)

    def _motor_type_changed(self, _index):
        key = self.motor_type_selector.currentData()
        self.motor_type_value.setText(self.motor_type_selector.currentText())

        if not key:
            return

        # Selecting a known motor type also selects its validated recipe.
        if key != self.BENCHMARK_KEY:
            index = self.recipe_selector.findData(key)
            if index >= 0:
                self.recipe_selector.setCurrentIndex(index)
        else:
            index = self.recipe_selector.findData(self.BENCHMARK_KEY)
            if index >= 0:
                self.recipe_selector.setCurrentIndex(index)

    def _set_ready_state(self):
        if self.breakin_controller:
            self.status.setText("READY / CONTROLLER CONNECTED")
        else:
            self.status.setText("ERROR / CONTROLLER NOT AVAILABLE")
        if self.motor_type_selector.count():
            self.motor_type_selector.setCurrentIndex(0)
        elif self.recipe_selector.count():
            self._recipe_changed(0)

    def _set_benchmark_vehicle_assumptions(self):
        self.vehicle_weight_value.setText(f"{self.BENCHMARK_VEHICLE_WEIGHT_G:.0f} g")
        self.tire_value.setText(f"{self.BENCHMARK_TIRE_DIAMETER_MM:.0f} mm")
        self.gear_ratio_value.setText(f"{self.BENCHMARK_GEAR_RATIO:.1f}:1")

    def _recipe_changed(self, _index):
        name = self.recipe_selector.currentData()
        if name == self.BENCHMARK_KEY:
            self.description.setText(
                "Standalone 3 V motor benchmark. No break-in stages are executed. "
                "The test holds approximately 3.00 V using closed-loop PWM control for 10 seconds. "
                "Vehicle estimate assumes 24 mm tires and 3.5:1 gearing; "
                "course, roller, brake and grip factors are excluded."
            )
            self.brush_value.setText("UNKNOWN")
            self.objective_value.setText("MEASUREMENT")
            self.target_rpm_value.setText("--")
            self.torque_priority_value.setText("0.50")
            self.benchmark_value.setText("3.00 V / 10 s")
            self._set_benchmark_vehicle_assumptions()
            safety = self.recipe_engine.safety()
            self.safety_value.setText(
                f"{safety.get('max_current', 5.0):g} A / "
                f"{safety.get('max_motor_temperature', 70.0):g} °C"
            )
            self.phase_list.clear()
            self.phase_list.addItem("BENCHMARK_3V_TEST: closed-loop 3.00 V / 10s")
            self.phase_list.addItem("VEHICLE: 24 mm tire / 3.5:1")
            self.phase_list.addItem("OTHER FACTORS: EXCLUDED")
            return

        recipe = self.selected_recipe()
        if recipe is None:
            return
        self.description.setText(recipe.description or "-")
        self.motor_type_value.setText(self.motor_type_selector.currentText())
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
        self.vehicle_weight_value.setText("--")
        self.tire_value.setText("--")
        self.gear_ratio_value.setText("--")
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

        self.last_benchmark_report = ""
        self.last_benchmark_results = None
        self.copy_benchmark_button.setEnabled(False)
        self.benchmark_detail_display.setText("--")

        label = "MOTOR BENCHMARK TEST" if is_benchmark else f"BREAK-IN / {recipe.name}"
        self.status.setText(f"RUNNING / {label}")
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.recipe_selector.setEnabled(False)
        self.motor_type_selector.setEnabled(False)
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
        self.motor_type_selector.setEnabled(True)

    def on_breakin_complete(self, result):
        is_benchmark = self.recipe_selector.currentData() == self.BENCHMARK_KEY
        self.display_analysis_result(result, benchmark=is_benchmark)
        self.status.setText(
            "MOTOR BENCHMARK COMPLETE" if is_benchmark else "BREAK-IN COMPLETE / BENCHMARK FINISHED"
        )

    def on_breakin_failed(self, message):
        self.status.setText(f"ERROR / {message}")
        self.result_display.setText("ERROR")
        self.stop_button.setEnabled(False)
        self.benchmark_detail_display.setText(message)

    def on_worker_finished(self):
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.recipe_selector.setEnabled(True)
        self.motor_type_selector.setEnabled(True)
        self.breakin_worker = None

    @staticmethod
    def _number(value, default=0.0):
        try:
            if hasattr(value, "value"):
                value = value.value
            return float(value)
        except (TypeError, ValueError):
            return default

    def display_analysis_result(self, result, benchmark=False):
        if result is None:
            self.result_display.setText("NO RESULT")
            return

        if benchmark:
            self._display_benchmark_result(result)
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
        self.lifecycle_display.setText("--")
        self.weight_display.setText("--")

    def _display_benchmark_result(self, result):
        """Display and retain an operator-friendly aggregate benchmark result."""
        self.last_benchmark_results = result
        measurements = list(getattr(self.breakin_controller, "measurements", []) or [])
        analysis_results = list(result) if isinstance(result, list) else []

        if not measurements and not analysis_results:
            self.result_display.setText("BENCHMARK COMPLETE / NO MEASUREMENTS")
            self.benchmark_detail_display.setText("No measurement samples were returned.")
            return

        def avg(values):
            values = [self._number(v) for v in values]
            return sum(values) / len(values) if values else 0.0

        def maximum(values):
            values = [self._number(v) for v in values]
            return max(values) if values else 0.0

        voltage_values = [getattr(m, "motor_voltage", 0.0) for m in measurements]
        current_values = [getattr(m, "current_avg", 0.0) for m in measurements]
        power_values = [getattr(m, "power", 0.0) for m in measurements]
        pwm_values = [getattr(m, "pwm", 0) for m in measurements]
        temperature_values = [getattr(m, "motor_temperature", 0.0) for m in measurements]

        rpm_values = []
        torque_values = []
        for item in analysis_results:
            performance = getattr(item, "performance", None)
            if performance is None:
                continue
            rpm_values.append(getattr(getattr(performance, "estimated_rpm", None), "value", 0.0))
            torque_values.append(getattr(getattr(performance, "estimated_torque", None), "value", 0.0))

        if not rpm_values:
            rpm_values = [self._number(v) * 5000.0 for v in voltage_values]
        if not torque_values:
            torque_values = [self._number(v) * 10.0 for v in current_values]

        avg_voltage = avg(voltage_values)
        avg_current = avg(current_values)
        avg_power = avg(power_values)
        avg_rpm = avg(rpm_values)
        avg_torque = avg(torque_values)
        avg_pwm = avg(pwm_values)
        max_current = maximum(current_values)
        max_temperature = maximum(temperature_values)

        elapsed_values = []
        for measurement in measurements:
            value = self._number(getattr(measurement, "elapsed_time", 0))
            if 0.0 <= value <= 86_400_000.0:
                elapsed_values.append(value)

        if elapsed_values:
            elapsed = max(0.0, max(elapsed_values) - min(elapsed_values)) / 1000.0
        else:
            elapsed = 0.0

        weight_estimate = estimate_vehicle_weight(
            avg_torque,
            tire_diameter_mm=self.BENCHMARK_TIRE_DIAMETER_MM,
            gear_ratio=self.BENCHMARK_GEAR_RATIO,
            reference_weight_g=self.BENCHMARK_VEHICLE_WEIGHT_G,
        )

        self.result_display.setText("3V BENCHMARK COMPLETE")
        self.rpm_display.setText(f"{avg_rpm:,.0f} rpm")
        self.torque_display.setText(f"{avg_torque:.2f} g·cm")
        self.lifecycle_display.setText("-- (benchmark only)")
        self.weight_display.setText(
            f"{weight_estimate.minimum_g:.0f}–{weight_estimate.maximum_g:.0f} g "
            f"(center {weight_estimate.center_g:.0f} g)"
        )
        self.benchmark_detail_display.setText(
            f"Avg {avg_voltage:.3f} V / {avg_current:.3f} A / {avg_power:.3f} W / "
            f"PWM {avg_pwm:.1f} | Max current {max_current:.3f} A | "
            f"Max temperature {max_temperature:.1f} °C | "
            f"Samples {len(measurements)} | {elapsed:.1f} s | "
            f"Motor {self.motor_type_selector.currentText()} | "
            f"Weight basis {weight_estimate.minimum_g:.0f}–{weight_estimate.maximum_g:.0f} g | "
            f"24 mm / 3.5:1 | Other factors excluded"
        )

        self.last_benchmark_report = self._build_benchmark_report(
            measurements=measurements,
            sample_count=len(measurements),
            elapsed=elapsed,
            avg_voltage=avg_voltage,
            avg_current=avg_current,
            avg_power=avg_power,
            avg_pwm=avg_pwm,
            avg_rpm=avg_rpm,
            avg_torque=avg_torque,
            max_current=max_current,
            max_temperature=max_temperature,
            motor_type=self.motor_type_selector.currentText(),
            weight_estimate=weight_estimate,
        )
        self.copy_benchmark_button.setEnabled(True)

    @staticmethod
    def _build_benchmark_report(
        *,
        measurements,
        sample_count,
        elapsed,
        avg_voltage,
        avg_current,
        avg_power,
        avg_pwm,
        avg_rpm,
        avg_torque,
        max_current,
        max_temperature,
        motor_type,
        weight_estimate,
    ):
        instance_id = "UNKNOWN"
        if measurements:
            instance_id = str(getattr(measurements[0], "instance_id", "UNKNOWN"))
        return (
            "MINI4WD AI SYSTEM - MOTOR BREAK-IN V3\n"
            "3V MOTOR BENCHMARK RESULT\n"
            "========================================\n"
            f"Motor type: {motor_type}\n"
            f"Instance: {instance_id}\n"
            "Target voltage: 3.000 V\n"
            f"Duration: {elapsed:.1f} s\n"
            f"Samples: {sample_count}\n"
            f"Average motor voltage: {avg_voltage:.3f} V\n"
            f"Average current: {avg_current:.3f} A\n"
            f"Average power: {avg_power:.3f} W\n"
            f"Average PWM: {avg_pwm:.1f}\n"
            f"Estimated RPM: {avg_rpm:,.0f} rpm\n"
            f"Estimated torque: {avg_torque:.2f} g·cm\n"
            f"Maximum current: {max_current:.3f} A\n"
            f"Maximum temperature: {max_temperature:.1f} °C\n"
            "----------------------------------------\n"
            f"Compatible vehicle weight: {weight_estimate.minimum_g:.0f}–{weight_estimate.maximum_g:.0f} g\n"
            f"Weight center estimate: {weight_estimate.center_g:.0f} g\n"
            "Tire diameter: 24 mm\n"
            "Gear ratio: 3.5:1\n"
            "Weight estimate: PROVISIONAL BENCHMARK CALIBRATION\n"
            "Other vehicle/course factors: EXCLUDED\n"
        )

    def copy_benchmark_result(self):
        if not self.last_benchmark_report:
            QMessageBox.information(self, "Benchmark", "No benchmark result is available to copy.")
            return
        clipboard = QApplication.clipboard()
        clipboard.setText(self.last_benchmark_report)
        self.status.setText("BENCHMARK RESULT COPIED TO CLIPBOARD")
