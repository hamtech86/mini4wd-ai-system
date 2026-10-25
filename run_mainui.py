"""Launch the MainUI desktop application.

Run from the repository root with: python3 run_mainui.py
This starts the UI only; it does not connect to the serial device or run a motor.
"""
import sys

from PyQt5.QtWidgets import QApplication

from app.application_builder import ApplicationBuilder
from app.main import MainWindow
from communication.serial_controller import SerialController


def main():
    serial_controller = SerialController()
    context = {
        "serial_controller": serial_controller,
        "breakin_controller": ApplicationBuilder(
            serial_controller
        ).build_breakin_controller(),
    }
    app = QApplication(sys.argv)
    window = MainWindow(context)
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
