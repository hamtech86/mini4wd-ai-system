"""Reusable launcher button for the Battery Database dialog."""
from PyQt5.QtWidgets import QPushButton
from ui.battery_database_ui import BatteryDatabaseDialog


def add_battery_database_button(main_window):
    """Add an always-enabled Battery DB button to the actual scroll content."""
    central = main_window.centralWidget()
    scroll = central.findChild(type(central.findChild(QPushButton))) if False else None
    # The base Motor UI uses a QScrollArea as the only child of the central widget.
    from PyQt5.QtWidgets import QScrollArea
    scroll = central.findChild(QScrollArea)
    if scroll is None or scroll.widget() is None or scroll.widget().layout() is None:
        raise RuntimeError("Motor UI scroll content is unavailable")
    content_layout = scroll.widget().layout()
    button = QPushButton("BATTERY DATABASE / INSTANCE & RESULT REGISTRATION", scroll.widget())
    button.setMinimumHeight(44)
    button.setEnabled(True)
    button.clicked.connect(lambda: BatteryDatabaseDialog(main_window.db_path, main_window).exec_())
    content_layout.addWidget(button)
    main_window.battery_database_button = button
    return button
