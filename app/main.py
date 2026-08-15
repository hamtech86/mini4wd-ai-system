"""MINI4WD AI SYSTEM / MOTOR_BREAKIN_V3 application entry point."""
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMessageBox, QGroupBox, QGridLayout, QLabel
from loguru import logger

from config import APP_NAME, APP_VERSION, LOG_DIR
from ui.main_window import MainWindow as BaseMainWindow
from communication.serial_controller import SerialController
from app.application_builder import ApplicationBuilder


class MainWindow(BaseMainWindow):
    """Main UI with the four operator-facing estimated performance values."""

    def __init__(self, context=None):
        super().__init__(context)
        self._build_estimated_result_panel()

    def _build_estimated_result_panel(self):
        # centralWidget() is the existing QWidget container, not a QScrollArea.
        # Keep the existing layout intact and append the estimated-result card.
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
    def _as_float(value, default=0.0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    def _estimated_values(self):
        controller = self.breakin_controller
        manager = getattr(controller, "measurement_manager", None) if controller else None
        measurement = getattr(manager, "last_measurement", None) if manager else None

        voltage = self._as_float(getattr(measurement, "motor_voltage", 0.0))
        current = self._as_float(getattr(measurement, "current_avg", 0.0))

        # MOTOR_BREAKIN_V3 current estimation contract.
        estimated_rpm = max(0.0, voltage * 5000.0)
        estimated_torque = max(0.0, current * 10.0)
        estimated_weight = max(0.0, estimated_torque * 12.0)

        peak = getattr(controller, "last_brush_peak_current", None) if controller else None
        if peak is None:
            data = getattr(self, "last_result_data", None)
            peak = self._number(
                data,
                "brush_peak_current",
                "peak_current",
                "peak_current_a",
                "max_current",
                "current_peak",
            )
        peak = self._as_float(peak, current)

        # Temporary brush-state score: +10=new, 0=peak/perfect, -10=failure.
        brush_score = max(-10.0, min(10.0, 10.0 - (peak * 5.0)))
        return estimated_rpm, estimated_torque, brush_score, estimated_weight

    def _refresh_estimated_values(self):
        if not hasattr(self, "estimated_result"):
            return
        rpm, torque, brush_score, weight = self._estimated_values()
        self.estimated_result["UNLOADED_RPM"].setText(f"{rpm:,.0f} rpm")
        self.estimated_result["TORQUE"].setText(f"{torque:.2f} g·cm")
        self.estimated_result["BRUSH_SCORE"].setText(f"{brush_score:+.1f} / +10 ～ -10")
        self.estimated_result["WEIGHT"].setText(f"{weight:.0f} g")

    def complete(self, data, benchmark):
        super().complete(data, benchmark)
        self._refresh_estimated_values()

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
