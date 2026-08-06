"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 main.py
=====================================================
Temporary UI integration entry point
"""

import sys
from PyQt5.QtWidgets import QApplication, QMessageBox

from loguru import logger

from config import APP_NAME, APP_VERSION, LOG_DIR
from ui.main_window import MainWindow


class ApplicationBuilder:
    """
    Temporary integration layer.

    This will become the dependency composition root for:
    - BreakinController
    - MeasurementManager
    - AnalysisEngine
    - SerialController
    """

    def build_context(self):
        return {}


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
        context = ApplicationBuilder().build_context()
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
