"""MINI4WD AI SYSTEM / MOTOR_BREAKIN_V3 application entry point."""
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication, QMessageBox, QGroupBox, QGridLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget, QTabWidget, QHBoxLayout, QComboBox, QCheckBox
from loguru import logger
from config import APP_NAME, APP_VERSION, LOG_DIR
from ui.main_window import MainWindow as BaseMainWindow
from communication.serial_controller import SerialController
from battery_system.serial import BatterySerial
from app.application_builder import ApplicationBuilder
from ui.resume_controls import install_resume_controls, bind_resume_api
from ui.battery_tab_ui import BatteryTab
from controllers.recipe_engine import RecipeEngine
from controllers.sequence_executor import SequenceExecutor
from controllers.breakin_sequence_adapter import BreakinSequenceAdapter

class MainWindow(BaseMainWindow):
    """Main UI with Motor Break-in / Recipe-Sequence and Battery tabs."""
    def __init__(self, context=None):
        super().__init__(context)
        bind_resume_api(type(self))
        install_resume_controls(self)
        self._extract_motor_page()
        self._build_estimated_result_panel()
        self.battery_serial_controller = context.get("battery_serial_controller") if context else None
        self._build_recipe_sequence_panel()
        self._build_integrated_ui()

    def _extract_motor_page(self):
        central = self.centralWidget()
        if central is None:
            return
        scroll = central.findChild(QScrollArea)
        self.motor_page = central
        self.motor_content = scroll.widget() if scroll is not None else None
        if self.motor_content is None:
            return
        layout = self.motor_content.layout()
        if layout is None:
            return
        for i in range(layout.count()):
            item = layout.itemAt(i)
            widget = item.widget() if item else None
            if widget is not None and widget.objectName() == "legacy_device_connection":
                layout.removeWidget(widget)
                widget.setParent(None)
                widget.deleteLater()
                break
        for i in range(layout.count() - 1, -1, -1):
            item = layout.itemAt(i)
            widget = item.widget() if item else None
            if widget is not None and getattr(widget, "objectName", lambda: "")() == "battery_database_button":
                layout.removeWidget(widget)
                widget.setParent(None)
                widget.deleteLater()

    def _build_integrated_ui(self):
        old_central = self.takeCentralWidget()
        if old_central is None:
            old_central = self.motor_page
        root = QWidget()
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(5, 5, 5, 5)

        device_box = QGroupBox("DEVICE CONNECTION")
        row = QGridLayout(device_box)
        self.motor_serial_status = QLabel("MOTOR: DISCONNECTED  /dev/ttyACM0")
        self.motor_connect = QPushButton("MOTOR CONNECT")
        self.motor_disconnect = QPushButton("MOTOR DISCONNECT")
        self.motor_disconnect.setEnabled(False)
        self.motor_connect.clicked.connect(self.connect_motor_serial)
        self.motor_disconnect.clicked.connect(self.disconnect_motor_serial)
        self.battery_serial_status = QLabel("BATTERY: DISCONNECTED  /dev/ttyUSB0")
        self.battery_connect = QPushButton("BATTERY CONNECT")
        self.battery_disconnect = QPushButton("BATTERY DISCONNECT")
        self.battery_disconnect.setEnabled(False)
        self.battery_connect.clicked.connect(self.connect_battery_serial)
        self.battery_disconnect.clicked.connect(self.disconnect_battery_serial)
        row.addWidget(self.motor_serial_status, 0, 0)
        row.addWidget(self.motor_connect, 0, 1)
        row.addWidget(self.motor_disconnect, 0, 2)
        row.addWidget(self.battery_serial_status, 1, 0)
        row.addWidget(self.battery_connect, 1, 1)
        row.addWidget(self.battery_disconnect, 1, 2)
        root_layout.addWidget(device_box)

        tabs = QTabWidget()
        tabs.addTab(old_central, "MOTOR BREAK-IN")
        self.battery_tab = BatteryTab(self.db_path, transport=self.battery_serial_controller, parent=self)
        tabs.addTab(self.battery_tab, "BATTERY")
        root_layout.addWidget(tabs, 1)
        self.setCentralWidget(root)

    def _motor_controller(self):
        controller = getattr(self, "serial_controller", None)
        if controller is None:
            controller = getattr(getattr(self, "breakin_controller", None), "serial_controller", None)
        return controller

    def connect_motor_serial(self):
        controller = self._motor_controller()
        if controller is None:
            QMessageBox.warning(self, "Motor Connection", "Motor serial controller is not available.")
            return
        if controller.connected:
            return
        if controller.connect():
            self.motor_serial_status.setText("MOTOR: CONNECTED  /dev/ttyACM0 @ 57600")
            self.motor_connect.setEnabled(False)
            self.motor_disconnect.setEnabled(True)
        else:
            self.motor_serial_status.setText("MOTOR: CONNECTION FAILED  /dev/ttyACM0")

    def disconnect_motor_serial(self):
        controller = self._motor_controller()
        if controller is not None:
            try:
                if controller.connected:
                    controller.stop_breakin()
            except Exception:
                logger.exception("Failed to stop motor before disconnect")
            try:
                controller.disconnect()
            except Exception:
                logger.exception("Failed to disconnect motor serial")
        if hasattr(self, "sequence_executor"):
            self.sequence_executor.stop("motor_disconnected")
        self.motor_serial_status.setText("MOTOR: DISCONNECTED  /dev/ttyACM0")
        self.motor_connect.setEnabled(True)
        self.motor_disconnect.setEnabled(False)

    def connect_battery_serial(self):
        controller = self.battery_serial_controller
        if controller is None:
            QMessageBox.warning(self, "Battery Connection", "Battery serial controller is not available.")
            return
        if controller.connected:
            return
        if not controller.connect():
            self.battery_serial_status.setText("BATTERY: CONNECTION FAILED  /dev/ttyUSB0")
            return
        self.battery_serial_status.setText("BATTERY: CONNECTED  /dev/ttyUSB0 @ 57600")
        self.battery_connect.setEnabled(False)
        self.battery_disconnect.setEnabled(True)
        self.battery_tab.set_connected(True)

    def disconnect_battery_serial(self):
        controller = self.battery_serial_controller
        if controller is not None:
            try:
                controller.stop()
            except Exception:
                pass
            try:
                controller.disconnect()
            except Exception:
                logger.exception("Failed to disconnect battery serial")
        self.battery_serial_status.setText("BATTERY: DISCONNECTED  /dev/ttyUSB0")
        self.battery_connect.setEnabled(True)
        self.battery_disconnect.setEnabled(False)
        self.battery_tab.set_connected(False)

    def _build_estimated_result_panel(self):
        content = self.motor_content
        layout = content.layout() if content is not None else None
        if layout is None:
            return
        self.estimated_result = {"UNLOADED_RPM": QLabel("--"), "TORQUE": QLabel("--"), "BRUSH_SCORE": QLabel("--"), "WEIGHT": QLabel("--")}
        box = QGroupBox("ESTIMATED PERFORMANCE / 推定値")
        grid = QGridLayout(box)
        labels = (("無負荷回転数（推定）", "UNLOADED_RPM"), ("トルク（推定）", "TORQUE"), ("ブラシピーク（推定）", "BRUSH_SCORE"), ("対応車重（推定）", "WEIGHT"))
        for index, (title, key) in enumerate(labels):
            card = QGroupBox(title)
            card_layout = QGridLayout(card)
            value = self.estimated_result[key]
            value.setAlignment(Qt.AlignCenter)
            value.setStyleSheet("font-size:16px;font-weight:bold;")
            card_layout.addWidget(value, 0, 0)
            grid.addWidget(card, index // 2, index % 2)
        layout.addWidget(box)

    def _build_recipe_sequence_panel(self):
        """Install Recipe preset -> ordered selectable Sequence -> executor controls."""
        self.recipe_engine = RecipeEngine()
        self.sequence_adapter = BreakinSequenceAdapter(self.breakin_controller)
        self.sequence_executor = SequenceExecutor(adapter=self.sequence_adapter)
        self.sequence_timer = QTimer(self)
        self.sequence_timer.setInterval(100)
        self.sequence_timer.timeout.connect(self._sequence_tick)

        box = QGroupBox("RECIPE / SEQUENCE")
        root = QVBoxLayout(box)
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("プリセット"))
        self.recipe_combo = QComboBox()
        self.recipe_combo.addItems(self.recipe_engine.names())
        toolbar.addWidget(self.recipe_combo, 1)
        self.recipe_load = QPushButton("読み込み")
        self.recipe_load.clicked.connect(lambda: self._load_recipe_sequence(self.recipe_combo.currentText()))
        toolbar.addWidget(self.recipe_load)
        root.addLayout(toolbar)

        actions = QHBoxLayout()
        self.sequence_all = QPushButton("全選択")
        self.sequence_none = QPushButton("全解除")
        self.sequence_all.clicked.connect(lambda: self._set_sequence_checks(True))
        self.sequence_none.clicked.connect(lambda: self._set_sequence_checks(False))
        self.sequence_execute = QPushButton("選択Sequenceを実行")
        self.sequence_stop = QPushButton("Sequence停止")
        self.sequence_stop.setEnabled(False)
        self.sequence_execute.clicked.connect(self._execute_selected_sequences)
        self.sequence_stop.clicked.connect(self._stop_sequences)
        actions.addWidget(self.sequence_all)
        actions.addWidget(self.sequence_none)
        actions.addStretch()
        actions.addWidget(self.sequence_execute)
        actions.addWidget(self.sequence_stop)
        root.addLayout(actions)

        self.sequence_status = QLabel("未実行")
        root.addWidget(self.sequence_status)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        self.sequence_layout = QVBoxLayout(body)
        self.sequence_layout.setContentsMargins(2, 2, 2, 2)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        self.sequence_checks = []
        layout = self.motor_content.layout() if self.motor_content is not None else None
        if layout is not None:
            layout.addWidget(box)
        self._load_recipe_sequence(self.recipe_combo.currentText())

    def _load_recipe_sequence(self, name):
        recipe = self.recipe_engine.get(name)
        if recipe is None:
            self.sequence_status.setText("レシピが見つかりません")
            return
        while self.sequence_layout.count():
            item = self.sequence_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.sequence_checks = []
        for sequence in recipe.sequences():
            check = QCheckBox(f"{sequence.order:02d} | {sequence.sequence_id} | {sequence.command} | {sequence.direction or '-'} | PWM {sequence.pwm if sequence.pwm is not None else '-'} | {sequence.duration_sec if sequence.duration_sec is not None else '-'}s")
            check.setChecked(sequence.enabled)
            self.sequence_layout.addWidget(check)
            self.sequence_checks.append((sequence.sequence_id, check))
        self.sequence_layout.addStretch()
        self.sequence_status.setText(f"{recipe.name}: {len(self.sequence_checks)} Sequence")

    def _set_sequence_checks(self, checked):
        for _, check in self.sequence_checks:
            check.setChecked(checked)

    def _execute_selected_sequences(self):
        recipe = self.recipe_engine.get(self.recipe_combo.currentText())
        if recipe is None:
            return
        enabled_ids = {sid for sid, check in self.sequence_checks if check.isChecked()}
        if not enabled_ids:
            self.sequence_status.setText("実施するSequenceが選択されていません")
            return
        controller = self._motor_controller()
        if controller is None or not getattr(controller, "connected", False):
            QMessageBox.warning(self, "Sequence", "先にMOTOR CONNECTを実行してください。")
            return
        self.sequence_executor.load_recipe(recipe, enabled_ids=enabled_ids)
        self.sequence_executor.start()
        self.sequence_timer.start()
        self.sequence_execute.setEnabled(False)
        self.sequence_stop.setEnabled(True)
        self.sequence_status.setText(f"実行中: {recipe.name}  0%")

    def _sequence_tick(self):
        try:
            current = self.sequence_executor.execute_current()
            if self.sequence_executor.is_complete():
                self.sequence_timer.stop()
                self.sequence_execute.setEnabled(True)
                self.sequence_stop.setEnabled(False)
                self.sequence_status.setText("完了: 100%")
                return
            self.sequence_status.setText(f"実行中: {self.sequence_executor.progress()}%  {current.sequence_id if current else ''}")
        except Exception as exc:
            self.sequence_timer.stop()
            self.sequence_executor.stop("error")
            self.sequence_execute.setEnabled(True)
            self.sequence_stop.setEnabled(False)
            self.sequence_status.setText(f"Sequence ERROR: {exc}")
            logger.exception("Sequence execution failed")
            QMessageBox.critical(self, "Sequence Error", str(exc))

    def _stop_sequences(self):
        self.sequence_timer.stop()
        self.sequence_executor.stop("operator_stop")
        self.sequence_execute.setEnabled(True)
        self.sequence_stop.setEnabled(False)
        self.sequence_status.setText("停止")

    @staticmethod
    def _as_float(value, default=0.0):
        try: return float(value)
        except (TypeError, ValueError): return default

    @staticmethod
    def _measurement_value(measurement, *names):
        if isinstance(measurement, dict):
            for name in names:
                value = measurement.get(name)
                if value is not None: return value
        else:
            for name in names:
                value = getattr(measurement, name, None)
                if value is not None: return value
        return None

    def _measurement_series(self):
        controller = self.breakin_controller
        return list(getattr(controller, "measurements", []) or []) if controller else []

    def _estimated_values(self):
        measurements = self._measurement_series()
        voltages = [self._as_float(self._measurement_value(m, "motor_voltage", "voltage"), 0.0) for m in measurements]
        currents = [abs(self._as_float(self._measurement_value(m, "current_avg", "current", "current1"), 0.0)) for m in measurements]
        voltages = [v for v in voltages if v > .01]; currents = [a for a in currents if a > .001]
        average_voltage = sum(voltages)/len(voltages) if voltages else 0.0
        average_current = sum(currents)/len(currents) if currents else 0.0
        peak_current = max(currents) if currents else 0.0
        estimated_rpm = max(0.0, average_voltage * 5000.0)
        estimated_torque = max(0.0, average_current * 10.0)
        weight_text = "データ不足"
        if estimated_torque > 0:
            reference_weight = estimated_torque * 12.0
            lo = max(115.0, reference_weight - 10.0); hi = min(155.0, reference_weight + 10.0); hi = max(hi, lo)
            weight_text = f"{lo:.0f}～{hi:.0f} g"
        brush_score = max(-10.0, min(10.0, 10.0 - peak_current * 5.0)) if currents else None
        if brush_score is None: brush_text = "データ不足"
        elif brush_score >= 7: brush_text = f"{brush_score:+.1f} / 10　新品寄り"
        elif brush_score >= 2: brush_text = f"{brush_score:+.1f} / 10　馴染み中"
        elif brush_score > -2: brush_text = f"{brush_score:+.1f} / 10　PEAK / 完璧"
        elif brush_score > -7: brush_text = f"{brush_score:+.1f} / 10　摩耗傾向"
        else: brush_text = f"{brush_score:+.1f} / 10　故障域"
        return estimated_rpm, estimated_torque, brush_text, weight_text

    def _refresh_estimated_values(self):
        if not hasattr(self, "estimated_result"): return
        rpm, torque, brush_text, weight_text = self._estimated_values()
        self.estimated_result["UNLOADED_RPM"].setText(f"{rpm:,.0f} rpm" if rpm > 0 else "データ不足")
        self.estimated_result["TORQUE"].setText(f"{torque:.2f} g·cm" if torque > 0 else "データ不足")
        self.estimated_result["BRUSH_SCORE"].setText(brush_text)
        self.estimated_result["WEIGHT"].setText(weight_text)

    def complete(self, data, benchmark):
        super().complete(data, benchmark)
        self._refresh_estimated_values()

    def failed(self, message):
        super().failed(message)
        if hasattr(self, "estimated_result"):
            for value in self.estimated_result.values(): value.setText("NOT AVAILABLE")

class ApplicationRuntimeBuilder:
    MOTOR_PORT = "/dev/ttyACM0"
    BATTERY_PORT = "/dev/ttyUSB0"
    SERIAL_BAUDRATE = 57600
    def __init__(self): self.serial_controller = None; self.battery_serial_controller = None
    def build_context(self):
        self.serial_controller = SerialController(serial_port=self.MOTOR_PORT, baudrate=self.SERIAL_BAUDRATE)
        self.battery_serial_controller = BatterySerial(port=self.BATTERY_PORT, baudrate=self.SERIAL_BAUDRATE)
        builder = ApplicationBuilder(serial_controller=self.serial_controller)
        return {"serial_controller": self.serial_controller, "breakin_controller": builder.build_breakin_controller(), "serial_connected": False, "battery_serial_controller": self.battery_serial_controller}
    def close(self):
        for controller in (self.serial_controller, self.battery_serial_controller):
            if controller is None: continue
            try:
                if controller.connected: controller.disconnect()
            except Exception: logger.exception("Failed to disconnect serial device during shutdown")

def setup_logger():
    logger.remove(); logger.add(sys.stdout, level="INFO", colorize=True); logger.add(LOG_DIR / "system.log", rotation="10 MB", retention=10, encoding="utf-8", level="DEBUG")

def main():
    setup_logger(); app = QApplication(sys.argv); app.setApplicationName(APP_NAME); app.setApplicationVersion(APP_VERSION); runtime = ApplicationRuntimeBuilder()
    try:
        context = runtime.build_context(); window = MainWindow(context); window.show(); app.aboutToQuit.connect(runtime.close); return app.exec()
    except Exception:
        logger.exception("Fatal Error"); runtime.close(); QMessageBox.critical(None, "Fatal Error", "致命的なエラーが発生しました。\nsystem.log を確認してください。"); return 1

if __name__ == "__main__": sys.exit(main())
