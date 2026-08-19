"""MINI4WD AI SYSTEM / MOTOR_BREAKIN_V3 application entry point."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QMessageBox,
    QGroupBox,
    QGridLayout,
    QLabel,
    QPushButton,
)
from loguru import logger

from config import APP_NAME, APP_VERSION, LOG_DIR
from ui.main_window import MainWindow as BaseMainWindow
from communication.serial_controller import SerialController
from app.application_builder import ApplicationBuilder
from ui.resume_controls import install_resume_controls, bind_resume_api
from ui.battery_database_ui import BatteryDatabaseDialog
from analysis.result_contract import build_estimated_result


class MainWindow(BaseMainWindow):
    """Main UI with operator-facing motor results and Battery DB registration.

    Analysis values are displayed from AnalysisResult through the shared
    presentation contract. Main.py does not recalculate RPM, torque, brush
    score, or supported weight from raw measurements.
    """

    def __init__(self, context=None):
        super().__init__(context)
        bind_resume_api(type(self))
        install_resume_controls(self)
        self._build_estimated_result_panel()
        self._build_battery_db_button()

    def _build_battery_db_button(self):
        content = self.centralWidget()
        layout = content.layout() if content is not None else None
        if layout is None:
            return
        button = QPushButton("BATTERY DATABASE / INSTANCE & RESULT REGISTRATION")
        button.setMinimumHeight(40)
        button.clicked.connect(self.open_battery_database)
        layout.addWidget(button)
        self.battery_database_button = button

    def open_battery_database(self):
        dialog = BatteryDatabaseDialog(self.db_path, self)
        dialog.exec_()

    def _build_estimated_result_panel(self):
        content = self.centralWidget()
        layout = content.layout() if content is not None else None
        if layout is None:
            return

        self.estimated_result = {
            "UNLOADED_RPM": QLabel("--"),
            "TORQUE": QLabel("--"),
            "BRUSH_SCORE": QLabel("--"),
            "WEIGHT": QLabel("--"),
        }
        box = QGroupBox("ESTIMATED PERFORMANCE / 推定値")
        grid = QGridLayout(box)
        labels = (
            ("無負荷回転数（推定）", "UNLOADED_RPM"),
            ("トルク（推定）", "TORQUE"),
            ("ブラシピーク（推定）", "BRUSH_SCORE"),
            ("対応車重（推定）", "WEIGHT"),
        )
        for index, (title, key) in enumerate(labels):
            card = QGroupBox(title)
            card_layout = QGridLayout(card)
            value = self.estimated_result[key]
            value.setAlignment(Qt.AlignCenter)
            value.setStyleSheet("font-size:16px;font-weight:bold;")
            card_layout.addWidget(value, 0, 0)
            grid.addWidget(card, index // 2, index % 2)
        layout.addWidget(box)

    @staticmethod
    def _latest_analysis_result(data):
        """Extract the most recent AnalysisResult from controller output."""
        if data is None:
            return None
        if isinstance(data, (list, tuple)):
            for item in reversed(data):
                if item is not None and hasattr(item, "performance"):
                    return item
            return None
        if hasattr(data, "performance"):
            return data
        if isinstance(data, dict):
            candidate = data.get("analysis_result") or data.get("result")
            if hasattr(candidate, "performance"):
                return candidate
        return None

    def _refresh_estimated_values(self, data=None):
        if not hasattr(self, "estimated_result"):
            return

        analysis_result = self._latest_analysis_result(
            data if data is not None else getattr(self, "last_result_data", None)
        )
        values = build_estimated_result(analysis_result)

        self.estimated_result["UNLOADED_RPM"].setText(values["estimated_no_load_rpm"])
        self.estimated_result["TORQUE"].setText(values["estimated_torque"])
        self.estimated_result["BRUSH_SCORE"].setText(values["brush_peak_score"])
        self.estimated_result["WEIGHT"].setText(values["estimated_supported_weight"])

    def complete(self, data, benchmark):
        super().complete(data, benchmark)
        self._refresh_estimated_values(data)

    def failed(self, message):
        super().failed(message)
        if hasattr(self, "estimated_result"):
            for value in self.estimated_result.values():
                value.setText("NOT AVAILABLE")


class ApplicationRuntimeBuilder:
    SERIAL_PORT = "/dev/ttyACM0"
    SERIAL_BAUDRATE = 57600

    def __init__(self):
        self.serial_controller = None

    def build_context(self):
        self.serial_controller = SerialController(
            serial_port=self.SERIAL_PORT,
            baudrate=self.SERIAL_BAUDRATE,
        )
        connected = self.serial_controller.connect()
        if connected:
            logger.info(
                "Arduino serial connected: {} @ {} baud",
                self.SERIAL_PORT,
                self.SERIAL_BAUDRATE,
            )
        else:
            logger.warning(
                "Arduino serial connection failed: {} @ {} baud",
                self.SERIAL_PORT,
                self.SERIAL_BAUDRATE,
            )

        builder = ApplicationBuilder(serial_controller=self.serial_controller)
        return {
            "serial_controller": self.serial_controller,
            "breakin_controller": builder.build_breakin_controller(),
            "serial_connected": connected,
        }

    def close(self):
        if self.serial_controller is None:
            return
        try:
            if self.serial_controller.connected:
                self.serial_controller.stop_breakin()
        except Exception:
            logger.exception("Failed to stop Arduino during shutdown")
        finally:
            try:
                self.serial_controller.disconnect()
            except Exception:
                logger.exception("Failed to disconnect Arduino serial port")


def setup_logger():
    logger.remove()
    logger.add(sys.stdout, level="INFO", colorize=True)
    logger.add(
        LOG_DIR / "system.log",
        rotation="10 MB",
        retention=10,
        encoding="utf-8",
        level="DEBUG",
    )


def main():
    setup_logger()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    runtime = ApplicationRuntimeBuilder()
    try:
        context = runtime.build_context()
        window = MainWindow(context)
        window.show()
        app.aboutToQuit.connect(runtime.close)
        return app.exec()
    except Exception:
        logger.exception("Fatal Error")
        runtime.close()
        QMessageBox.critical(
            None,
            "Fatal Error",
            "致命的なエラーが発生しました。\nsystem.log を確認してください。",
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
