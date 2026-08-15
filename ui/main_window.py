"""MOTOR_BREAKIN_V3 production operator UI."""

from __future__ import annotations

from PyQt5.QtCore import QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from controllers.recipe import (
    default_balance_recipe,
    default_speed_recipe,
    default_torque_recipe,
)


class BreakinWorker(QThread):
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
    """Single-screen production break-in/benchmark operator UI."""

    def __init__(self, context=None):
        super().__init__()
        self.context = context
        self.breakin_worker = None
        self._measurements = []

        if isinstance(context, dict):
            self.breakin_controller = context.get("breakin_controller")
        else:
            self.breakin_controller = getattr(context, "breakin_controller", None)

        self.setWindowTitle("MINI4WD AI SYSTEM - MOTOR BREAK-IN V3")
        self.resize(900, 650)
        self.timer = QTimer(self)
        self.timer.setInterval(250)
        self.timer.timeout.connect(self._refresh_live)
        self._build_ui()
        self._load_instances()
        self._set_ready()

    def _build_ui(self):
        root = QWidget()
        main = QVBoxLayout(root)

        title = QLabel("MOTOR BREAK-IN / ELECTRICAL BENCHMARK")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        main.addWidget(title)

        self.status = QLabel("READY")
        self.status.setStyleSheet("font-size: 15px; font-weight: bold;")
        main.addWidget(self.status)

        selection = QGroupBox("MOTOR INSTANCE / RECIPE")
        form = QFormLayout(selection)
        self.instance_selector = QComboBox()
        self.recipe_selector = QComboBox()
        self.recipe_selector.addItem("TORQUE TUNE / TORQUE", "TORQUE")
        self.recipe_selector.addItem("SPEED", "SPEED")
        self.recipe_selector.addItem("BALANCE", "BALANCE")
        form.addRow("Motor Instance", self.instance_selector)
        form.addRow("Break-in Recipe", self.recipe_selector)
        main.addWidget(selection)

        live = QGroupBox("LIVE MEASUREMENT")
        live_layout = QHBoxLayout(live)
        self.live_state = QLabel("--")
        self.live_direction = QLabel("--")
        self.live_pwm = QLabel("--")
        self.live_voltage = QLabel("--")
        self.live_current = QLabel("--")
        self.live_power = QLabel("--")
        self.live_rpm = QLabel("REFERENCE --")
        for name, value in (
            ("State", self.live_state),
            ("Dir", self.live_direction),
            ("PWM", self.live_pwm),
            ("Motor V", self.live_voltage),
            ("Current", self.live_current),
            ("Power", self.live_power),
            ("KY-024 RPM", self.live_rpm),
        ):
            block = QVBoxLayout()
            block.addWidget(QLabel(name))
            block.addWidget(value)
            live_layout.addLayout(block)
        main.addWidget(live)

        controls = QHBoxLayout()
        self.start_button = QPushButton("START BREAK-IN")
        self.stop_button = QPushButton("EMERGENCY STOP")
        self.stop_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_breakin)
        self.stop_button.clicked.connect(self.stop_breakin)
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        main.addLayout(controls)

        result = QGroupBox("BENCHMARK / ANALYSIS")
        result_form = QFormLayout(result)
        self.result_summary = QLabel("--")
        self.estimated_rpm = QLabel("--")
        self.estimated_torque = QLabel("--")
        self.brush_state = QLabel("--")
        self.brush_confidence = QLabel("--")
        self.compatible_weight = QLabel("--")
        self.sample_count = QLabel("0")
        self.data_quality = QLabel("--")
        result_form.addRow("Summary", self.result_summary)
        result_form.addRow("Estimated no-load RPM", self.estimated_rpm)
        result_form.addRow("Estimated torque", self.estimated_torque)
        result_form.addRow("Brush condition", self.brush_state)
        result_form.addRow("Brush confidence", self.brush_confidence)
        result_form.addRow("Corresponding vehicle weight", self.compatible_weight)
        result_form.addRow("Samples", self.sample_count)
        result_form.addRow("Data quality", self.data_quality)
        main.addWidget(result)

        self.setCentralWidget(root)

    def _database(self):
        return getattr(self.breakin_controller, "database", None)

    def _load_instances(self):
        self.instance_selector.clear()
        db = self._database()
        if db is None:
            self.instance_selector.addItem("DATABASE NOT AVAILABLE", None)
            return
        try:
            rows = db.execute(
                "SELECT instance_id, serial_number, nickname, status "
                "FROM motor_instance WHERE is_deleted=0 ORDER BY instance_id"
            ).fetchall()
        except Exception as exc:
            self.instance_selector.addItem(f"DATABASE ERROR: {exc}", None)
            return
        for row in rows:
            label = f"#{row[0]} {row[1] or ''} {row[2] or ''}".strip()
            self.instance_selector.addItem(label, int(row[0]))
        if self.instance_selector.count() == 0:
            self.instance_selector.addItem("NO MOTOR INSTANCE", None)

    def _set_ready(self):
        if self.breakin_controller:
            self.status.setText("READY / CONTROLLER CONNECTED")
        else:
            self.status.setText("ERROR / CONTROLLER NOT AVAILABLE")
        self._refresh_live()

    def _recipe(self):
        name = self.recipe_selector.currentData()
        if name == "TORQUE":
            return default_torque_recipe()
        if name == "SPEED":
            return default_speed_recipe()
        return default_balance_recipe()

    @staticmethod
    def _value(obj, name, default=0.0):
        try:
            return getattr(obj, name, default)
        except Exception:
            return default

    def _refresh_live(self):
        controller = self.breakin_controller
        manager = getattr(controller, "measurement_manager", None) if controller else None
        measurement = getattr(manager, "last_measurement", None) if manager else None
        if measurement is None:
            return
        self.live_state.setText(str(self._value(measurement, "state", "--")))
        self.live_direction.setText(str(self._value(measurement, "direction", "--")))
        self.live_pwm.setText(str(self._value(measurement, "pwm", 0)))
        self.live_voltage.setText(f"{abs(float(self._value(measurement, 'motor_voltage', 0.0))):.3f} V")
        self.live_current.setText(f"{abs(float(self._value(measurement, 'current_avg', 0.0))):.3f} A")
        self.live_power.setText(f"{abs(float(self._value(measurement, 'power', 0.0))):.3f} W")
        # Reference only. It is deliberately not fed to formal analysis.
        magnetic = self._value(measurement, "magnetic_level", 0.0)
        self.live_rpm.setText(f"REFERENCE {float(magnetic):.0f}")

    def start_breakin(self):
        if not self.breakin_controller:
            QMessageBox.warning(self, "Controller", "BreakinController is unavailable.")
            return
        if self.breakin_worker and self.breakin_worker.isRunning():
            return
        instance_id = self.instance_selector.currentData()
        if instance_id is None:
            QMessageBox.warning(self, "Motor Instance", "Select a valid Motor Instance.")
            return

        recipe = self._recipe()
        self._measurements = []
        self.status.setText(
            f"RUNNING / INSTANCE #{instance_id} / {recipe.name}"
        )
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.instance_selector.setEnabled(False)
        self.recipe_selector.setEnabled(False)
        self.result_summary.setText("RUNNING")
        self.timer.start()
        self.breakin_worker = BreakinWorker(
            self.breakin_controller,
            recipe,
            int(instance_id),
        )
        self.breakin_worker.completed.connect(self.on_complete)
        self.breakin_worker.failed.connect(self.on_failed)
        self.breakin_worker.finished.connect(self.on_finished)
        self.breakin_worker.start()

    def stop_breakin(self):
        if self.breakin_controller:
            self.breakin_controller.emergency_stop()
        self.status.setText("STOPPED / EMERGENCY STOP")
        self._enable_controls()

    def _enable_controls(self):
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.instance_selector.setEnabled(True)
        self.recipe_selector.setEnabled(True)

    def on_complete(self, result):
        self.timer.stop()
        self._refresh_live()
        measurements = list(getattr(self.breakin_controller, "measurements", []) or [])
        self.sample_count.setText(str(len(measurements)))
        if not result:
            self.result_summary.setText("COMPLETE / NO ANALYSIS RESULT")
            return

        latest = result[-1] if isinstance(result, list) else result
        performance = getattr(latest, "performance", None)
        brush = getattr(latest, "brush", None)
        validation = getattr(latest, "validation", None)

        if performance is not None:
            rpm = getattr(performance, "estimated_rpm", None)
            torque = getattr(performance, "estimated_torque", None)
            weight = getattr(performance, "estimated_weight", None)
            self.estimated_rpm.setText(
                f"{getattr(rpm, 'value', 0.0):,.0f} rpm / confidence {getattr(rpm, 'confidence', 0.0):.2f}"
            )
            self.estimated_torque.setText(
                f"{getattr(torque, 'value', 0.0):.2f} g·cm / confidence {getattr(torque, 'confidence', 0.0):.2f}"
            )
            self.compatible_weight.setText(
                f"{getattr(weight, 'value', 0.0):.0f} g / confidence {getattr(weight, 'confidence', 0.0):.2f}"
            )

        if brush is not None:
            self.brush_state.setText(str(getattr(brush, "brush_condition", "UNKNOWN")))
            self.brush_confidence.setText(
                f"{getattr(brush, 'confidence', 0.0):.2f} / {getattr(brush, 'explanation', '')}"
            )

        if validation is not None:
            self.data_quality.setText(
                f"valid={getattr(validation, 'valid', False)} / "
                f"quality={getattr(validation, 'quality_score', 0.0):.2f}"
            )

        self.result_summary.setText("BENCHMARK COMPLETE / ELECTRICAL ANALYSIS")
        self.status.setText("BREAK-IN COMPLETE / RESULT SAVED")

    def on_failed(self, message):
        self.timer.stop()
        self.status.setText(f"ERROR / {message}")
        self.result_summary.setText("ERROR")

    def on_finished(self):
        self.timer.stop()
        self._enable_controls()
        self.breakin_worker = None
