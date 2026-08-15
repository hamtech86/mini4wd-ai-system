# ============================================================
# motor_manager_ui.py
# Motor Database System
# Revision 2
# Motor Instance Management UI
# ============================================================

import sys
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QMessageBox,
)


ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(ROOT))

from database.manager.database_manager import DatabaseManager


class MotorManagerUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Motor Instance Manager")
        self.resize(760, 560)
        self.db = DatabaseManager(str(ROOT / "database" / "mini4wd.db"))
        self.editing_instance_id = None
        self.setup_ui()
        self.load_models()
        self.load_instances()

    def setup_ui(self):
        layout = QVBoxLayout()

        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Motor Model"))
        self.model_box = QComboBox()
        row1.addWidget(self.model_box)
        layout.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Serial Number"))
        self.serial_edit = QLineEdit()
        row2.addWidget(self.serial_edit)
        layout.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(QLabel("Nickname"))
        self.name_edit = QLineEdit()
        row3.addWidget(self.name_edit)
        layout.addLayout(row3)

        buttons = QHBoxLayout()
        self.register_button = QPushButton("Register")
        self.register_button.clicked.connect(self.register_motor)
        buttons.addWidget(self.register_button)

        self.update_button = QPushButton("Update Selected")
        self.update_button.clicked.connect(self.update_selected)
        self.update_button.setEnabled(False)
        buttons.addWidget(self.update_button)

        self.clear_button = QPushButton("Clear / New")
        self.clear_button.clicked.connect(self.clear_editor)
        buttons.addWidget(self.clear_button)
        layout.addLayout(buttons)

        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            ["ID", "Model ID", "Serial", "Nickname", "Status"]
        )
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.table)

        self.setLayout(layout)

    def load_models(self):
        self.model_box.clear()
        for model in self.db.motor.get_all():
            self.model_box.addItem(model["name"], model["motor_model_id"])

    def register_motor(self):
        model_id = self.model_box.currentData()
        if model_id is None:
            QMessageBox.warning(self, "Motor Model", "Motor Modelを選択してください。")
            return

        data = {
            "motor_model_id": model_id,
            "serial_number": self.serial_edit.text().strip(),
            "nickname": self.name_edit.text().strip(),
            "status": "NEW",
        }
        instance_id = self.db.motor_instance.create(data)
        QMessageBox.information(self, "Complete", f"Motor Created ID={instance_id}")
        self.load_instances()
        self.clear_editor()

    def load_instances(self):
        rows = self.db.motor_instance.get_all_active()
        self.table.setRowCount(len(rows))
        for r, data in enumerate(rows):
            values = [
                data["instance_id"],
                data["motor_model_id"],
                data["serial_number"],
                data["nickname"],
                data["status"],
            ]
            for c, value in enumerate(values):
                self.table.setItem(r, c, QTableWidgetItem(str(value or "")))
        self.table.resizeColumnsToContents()

    def on_selection_changed(self):
        row = self.table.currentRow()
        if row < 0:
            return

        instance_id_item = self.table.item(row, 0)
        if instance_id_item is None:
            return
        try:
            self.editing_instance_id = int(instance_id_item.text())
        except ValueError:
            self.clear_editor()
            return

        model_id = self.table.item(row, 1).text()
        serial = self.table.item(row, 2).text()
        nickname = self.table.item(row, 3).text()

        model_index = self.model_box.findData(int(model_id))
        if model_index >= 0:
            self.model_box.setCurrentIndex(model_index)
        self.serial_edit.setText(serial)
        self.name_edit.setText(nickname)
        self.update_button.setEnabled(True)

    def update_selected(self):
        if self.editing_instance_id is None:
            return

        model_id = self.model_box.currentData()
        if model_id is None:
            QMessageBox.warning(self, "Motor Model", "Motor Modelを選択してください。")
            return

        data = {
            "motor_model_id": model_id,
            "serial_number": self.serial_edit.text().strip(),
            "nickname": self.name_edit.text().strip(),
        }
        self.db.motor_instance.update_instance(self.editing_instance_id, data)
        self.db.commit()
        QMessageBox.information(
            self,
            "Updated",
            f"Motor Instance ID={self.editing_instance_id} を更新しました。",
        )
        self.load_instances()
        self.clear_editor()

    def clear_editor(self):
        self.editing_instance_id = None
        self.serial_edit.clear()
        self.name_edit.clear()
        if self.model_box.count():
            self.model_box.setCurrentIndex(0)
        self.table.clearSelection()
        self.update_button.setEnabled(False)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MotorManagerUI()
    window.show()
    sys.exit(app.exec_())
