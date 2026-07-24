# ============================================================
# motor_manager_ui.py
# Motor Database System
# Revision 1
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
    QMessageBox
)


# project root
ROOT = Path(__file__).resolve().parents[3]

sys.path.append(
    str(ROOT)
)


from database.manager.database_manager import DatabaseManager



class MotorManagerUI(QWidget):


    def __init__(self):

        super().__init__()


        self.setWindowTitle(
            "Motor Instance Manager"
        )

        self.resize(
            700,
            500
        )


        self.db = DatabaseManager(
            str(ROOT / "database" / "mini4wd.db")
        )


        self.setup_ui()


        self.load_models()

        self.load_instances()



    def setup_ui(self):

        layout = QVBoxLayout()


        # -----------------------------
        # Motor model
        # -----------------------------

        row1 = QHBoxLayout()

        row1.addWidget(
            QLabel("Motor Model")
        )


        self.model_box = QComboBox()

        row1.addWidget(
            self.model_box
        )


        layout.addLayout(row1)



        # -----------------------------
        # Serial
        # -----------------------------

        row2 = QHBoxLayout()

        row2.addWidget(
            QLabel("Serial Number")
        )


        self.serial_edit = QLineEdit()


        row2.addWidget(
            self.serial_edit
        )


        layout.addLayout(row2)



        # -----------------------------
        # Nickname
        # -----------------------------

        row3 = QHBoxLayout()


        row3.addWidget(
            QLabel("Nickname")
        )


        self.name_edit = QLineEdit()


        row3.addWidget(
            self.name_edit
        )


        layout.addLayout(row3)



        # -----------------------------
        # Register button
        # -----------------------------

        self.register_button = QPushButton(
            "Register"
        )


        self.register_button.clicked.connect(
            self.register_motor
        )


        layout.addWidget(
            self.register_button
        )



        # -----------------------------
        # Table
        # -----------------------------

        self.table = QTableWidget()


        self.table.setColumnCount(5)


        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                "Model ID",
                "Serial",
                "Nickname",
                "Status"
            ]
        )


        layout.addWidget(
            self.table
        )


        self.setLayout(
            layout
        )



    def load_models(self):

        models = self.db.motor.get_all()


        for m in models:

            self.model_box.addItem(
                m["name"],
                m["motor_model_id"]
            )



    def register_motor(self):

        model_id = self.model_box.currentData()


        data = {

            "motor_model_id":
                model_id,

            "serial_number":
                self.serial_edit.text(),

            "nickname":
                self.name_edit.text(),

            "status":
                "NEW"

        }


        instance_id = self.db.motor_instance.create(
            data
        )


        QMessageBox.information(
            self,
            "Complete",
            f"Motor Created ID={instance_id}"
        )


        self.load_instances()



    def load_instances(self):

        rows = self.db.motor_instance.get_all_active()


        self.table.setRowCount(
            len(rows)
        )


        for r, data in enumerate(rows):

            values = [

                data["instance_id"],

                data["motor_model_id"],

                data["serial_number"],

                data["nickname"],

                data["status"]

            ]


            for c, value in enumerate(values):

                self.table.setItem(
                    r,
                    c,
                    QTableWidgetItem(
                        str(value)
                    )
                )



if __name__ == "__main__":


    app = QApplication(
        sys.argv
    )


    window = MotorManagerUI()

    window.show()


    sys.exit(
        app.exec_()
    )
