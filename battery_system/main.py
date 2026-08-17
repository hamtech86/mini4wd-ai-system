"""Standalone launcher for the battery evaluation UI."""
import sys
from PyQt5.QtWidgets import QApplication

from battery_system.ui import BatteryEvaluationWindow


def main():
    app = QApplication(sys.argv)
    window = BatteryEvaluationWindow()
    window.show()
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
