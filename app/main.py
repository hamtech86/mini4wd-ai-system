"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 main.py
=====================================================
Application entry point
"""

import sys
from pathlib import Path

# Allow execution with: python3 app/main.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt5.QtWidgets import QApplication, QMessageBox

from loguru import logger

from config import APP_NAME, APP_VERSION, LOG_DIR
from ui.main_window import MainWindow
from communication.serial_controller import SerialController
from app.application_builder import ApplicationBuilder


class ApplicationRuntimeBuilder:
    """Create application dependency context."""

    def build_context(self):
        serial_controller = SerialController(
            serial_port="/dev/ttyACM0"
        )

        if serial_controller.connect():
            logger.info("Arduino serial connected")
        else:
            logger.warning("Arduino serial connection failed")

        builder = ApplicationBuilder(
            serial_controller=serial_controller
        )

        return {
            "serial_controller": serial_controller,
            "breakin_controller": builder.build_breakin_controller(),
        }


def setup_logger() -> None:
    logger.remove()
    logger.add(sys.stdout, level="INFO", colorize=True)
    logger.add(
        LOG_DIR / "system.log",
        rotation="10 MB",
        retention=10,
        encoding="utf-8",
        level="DEBUG",
    )


def main() -> int:
    setup_logger()

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    try:
        context = ApplicationRuntimeBuilder().build_context()
        window = MainWindow(context)
        window.show()
        return app.exec()

    except Exception:
        logger.exception("Fatal Error")
        QMessageBox.critical(
            None,
            "Fatal Error",
            "致命的なエラーが発生しました。\nsystem.log を確認してください。"
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
