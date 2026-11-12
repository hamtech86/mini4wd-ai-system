"""Launch the MainUI desktop application.

Run from the repository root with: python3 run_mainui.py
This starts the UI only; it does not connect to the serial device or run a motor.
"""
import sys

from PyQt5.QtWidgets import QApplication

from app.main import MainWindow, build_application_context


def main():
    # Use the same dependency factory as app.main so Motor and Battery
    # controllers are both injected into the integrated UI. Constructing the
    # transports does not open either serial port; connection remains explicit.
    context = build_application_context()
    app = QApplication(sys.argv)
    window = MainWindow(context=context)
    window.show()
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
