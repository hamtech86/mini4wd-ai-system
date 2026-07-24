"""
=====================================================
 MINI4WD AI SYSTEM
 MOTOR_BREAKIN_V3
 main.py
=====================================================
アプリケーション エントリーポイント
"""

import sys
from PyQt5.QtWidgets import QApplication, QMessageBox

from loguru import logger

from config import (
    APP_NAME,
    APP_VERSION,
    LOG_DIR,
)

# メインウィンドウ
from ui.main_window import MainWindow


def setup_logger() -> None:
    """
    Loguru 初期化
    """

    logger.remove()

    logger.add(
        sys.stdout,
        level="INFO",
        colorize=True,
    )

    logger.add(
        LOG_DIR / "system.log",
        rotation="10 MB",
        retention=10,
        encoding="utf-8",
        level="DEBUG",
    )


def main() -> int:
    """
    アプリケーション開始
    """

    setup_logger()

    logger.info(f"{APP_NAME} {APP_VERSION} Starting...")

    app = QApplication(sys.argv)

    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)

    try:

        window = MainWindow()
        window.show()

        result = app.exec()

        logger.info("Application Closed")

        return result

    except Exception:

        logger.exception("Fatal Error")

        QMessageBox.critical(
            None,
            "Fatal Error",
            "致命的なエラーが発生しました。\n"
            "system.log を確認してください。"
        )

        return 1


if __name__ == "__main__":
    sys.exit(main())

