# ============================================================
# motor_manager_ui.py
# MINI4WD AI SYSTEM
# Motor Instance Manager
# Revision 2
# ============================================================

import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(ROOT))

from database.manager.database_manager import DatabaseManager
from database.repository.motor_instance_repository import MotorInstanceRepository
from database.repository.motor_repository import MotorRepository


class MotorManagerUI(QWidget):
    """Motor Instanceを登録・編集・履歴確認・比較するUI。"""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Motor Instance Manager")
        self.resize(1100, 720)

        self.db = DatabaseManager(str(ROOT / "database" / "mini4wd.db"))
        self.db.connect()
        self.motor_repo = MotorRepository(self.db)
        self.instance_repo = MotorInstanceRepository(self.db)
        self.current_instance_id = None

        self.setup_ui()
        self.load_models()
        self.load_instances()

    # --------------------------------------------------------
    # UI
    # --------------------------------------------------------
    def setup_ui(self):
        root_layout = QVBoxLayout(self)

        header = QHBoxLayout()
        title = QLabel("Motor Instance Manager")
        title.setStyleSheet("font-size: 20px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh_all)
        header.addWidget(self.refresh_button)
        root_layout.addLayout(header)

        self.tabs = QTabWidget()
        self.instance_tab = QWidget()
        self.detail_tab = QWidget()
        self.compare_tab = QWidget()
        self.tabs.addTab(self.instance_tab, "Instances")
        self.tabs.addTab(self.detail_tab, "Detail / History")
        self.tabs.addTab(self.compare_tab, "Compare")
        root_layout.addWidget(self.tabs)

        self.setup_instance_tab()
        self.setup_detail_tab()
        self.setup_compare_tab()

    def setup_instance_tab(self):
        layout = QVBoxLayout(self.instance_tab)

        form_box = QGroupBox("Motor Instance")
        form = QFormLayout(form_box)

        self.model_box = QComboBox()
        form.addRow("Motor Model", self.model_box)

        self.serial_edit = QLineEdit()
        form.addRow("Serial Number", self.serial_edit)

        self.nickname_edit = QLineEdit()
        form.addRow("Nickname", self.nickname_edit)

        self.status_box = QComboBox()
        self.status_box.addItems(
            ["NEW", "ACTIVE", "MAINTENANCE", "RETIRED", "ARCHIVED"]
        )
        form.addRow("Status", self.status_box)

        self.health_box = QComboBox()
        self.health_box.addItems(["UNKNOWN", "GOOD", "WARNING", "BAD"])
        form.addRow("Health", self.health_box)

        self.purchase_edit = QLineEdit()
        self.purchase_edit.setPlaceholderText("YYYY-MM-DD")
        form.addRow("Purchase Date", self.purchase_edit)

        self.opened_edit = QLineEdit()
        self.opened_edit.setPlaceholderText("YYYY-MM-DD")
        form.addRow("Opened Date", self.opened_edit)

        layout.addWidget(form_box)

        buttons = QHBoxLayout()
        self.save_button = QPushButton("Register")
        self.save_button.clicked.connect(self.save_instance)
        buttons.addWidget(self.save_button)

        self.new_button = QPushButton("New")
        self.new_button.clicked.connect(self.clear_form)
        buttons.addWidget(self.new_button)

        self.delete_button = QPushButton("Retire / Delete")
        self.delete_button.clicked.connect(self.delete_instance)
        buttons.addWidget(self.delete_button)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.instance_table = QTableWidget()
        self.instance_table.setColumnCount(10)
        self.instance_table.setHorizontalHeaderLabels(
            [
                "ID",
                "Model",
                "Serial",
                "Nickname",
                "Status",
                "Health",
                "Latest Session",
                "Anomaly",
                "Created",
                "Updated",
            ]
        )
        self.instance_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.instance_table.setSelectionMode(QTableWidget.ExtendedSelection)
        self.instance_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.instance_table.cellDoubleClicked.connect(self.open_selected_instance)
        layout.addWidget(self.instance_table)

        hint = QLabel("Double-click: edit/detail / Ctrl-click: multiple selection for comparison")
        hint.setStyleSheet("color: #666;")
        layout.addWidget(hint)

    def setup_detail_tab(self):
        layout = QVBoxLayout(self.detail_tab)

        self.detail_title = QLabel("No instance selected")
        self.detail_title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(self.detail_title)

        self.detail_info = QTableWidget()
        self.detail_info.setColumnCount(2)
        self.detail_info.setHorizontalHeaderLabels(["Field", "Value"])
        self.detail_info.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.detail_info)

        history_label = QLabel("Measurement Session / Break-in History")
        history_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(history_label)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(9)
        self.history_table.setHorizontalHeaderLabels(
            [
                "Session",
                "Device",
                "Device Model",
                "Start",
                "End",
                "Result",
                "Logs",
                "Last RPM",
                "Last Current mA",
            ]
        )
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.history_table)

    def setup_compare_tab(self):
        layout = QVBoxLayout(self.compare_tab)

        top = QHBoxLayout()
        top.addWidget(QLabel("Select multiple instances in Instances tab, then:"))
        self.compare_button = QPushButton("Compare Selected")
        self.compare_button.clicked.connect(self.compare_selected)
        top.addWidget(self.compare_button)
        top.addStretch()
        layout.addLayout(top)

        self.compare_table = QTableWidget()
        self.compare_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.compare_table)

    # --------------------------------------------------------
    # Data loading
    # --------------------------------------------------------
    def load_models(self):
        self.model_box.clear()
        for model in self.motor_repo.get_all():
            self.model_box.addItem(
                str(model.get("name", model.get("motor_model_id"))),
                model.get("motor_model_id"),
            )

    def load_instances(self):
        try:
            rows = self.instance_repo.get_list_view()
        except Exception:
            rows = self.instance_repo.get_all_active()

        self.instance_table.setRowCount(len(rows))
        for r, data in enumerate(rows):
            values = [
                data.get("instance_id", ""),
                data.get("motor_name", data.get("motor_model_id", "")),
                data.get("serial_number", ""),
                data.get("nickname", ""),
                data.get("status", ""),
                data.get("health_status", ""),
                data.get("latest_session_id", ""),
                data.get("anomaly_count", 0),
                data.get("created_at", ""),
                data.get("updated_at", ""),
            ]
            for c, value in enumerate(values):
                item = QTableWidgetItem("" if value is None else str(value))
                if c == 0:
                    item.setData(Qt.UserRole, data.get("instance_id"))
                self.instance_table.setItem(r, c, item)

        self.instance_table.resizeColumnsToContents()

    def refresh_all(self):
        self.load_models()
        self.load_instances()
        if self.current_instance_id is not None:
            self.show_instance_detail(self.current_instance_id)

    # --------------------------------------------------------
    # Registration / editing
    # --------------------------------------------------------
    def collect_form_data(self):
        model_id = self.model_box.currentData()
        if model_id is None:
            raise ValueError("Motor Model is required.")

        serial = self.serial_edit.text().strip()
        nickname = self.nickname_edit.text().strip()
        if not serial and not nickname:
            raise ValueError("Serial Number or Nickname is required.")

        return {
            "motor_model_id": model_id,
            "serial_number": serial,
            "nickname": nickname,
            "status": self.status_box.currentText(),
            "health_status": self.health_box.currentText(),
            "purchase_date": self.purchase_edit.text().strip() or None,
            "opened_date": self.opened_edit.text().strip() or None,
        }

    def supported_instance_data(self, data):
        """既存DBの列だけを更新し、世代差によるUI破壊を防ぐ。"""
        cursor = self.db.execute("PRAGMA table_info(motor_instance)")
        columns = {row[1] for row in cursor.fetchall()}
        return {key: value for key, value in data.items() if key in columns}

    def save_instance(self):
        try:
            data = self.supported_instance_data(self.collect_form_data())
            if not data.get("motor_model_id"):
                raise ValueError("Motor Model is required.")

            if self.current_instance_id is None:
                instance_id = self.instance_repo.create(data)
                message = f"Motor Instance created: {instance_id}"
            else:
                self.instance_repo.update_instance(self.current_instance_id, data)
                instance_id = self.current_instance_id
                message = f"Motor Instance updated: {instance_id}"

            self.current_instance_id = instance_id
            self.load_instances()
            self.show_instance_detail(instance_id)
            QMessageBox.information(self, "Complete", message)
        except Exception as exc:
            QMessageBox.critical(self, "Save Error", str(exc))

    def clear_form(self):
        self.current_instance_id = None
        self.model_box.setCurrentIndex(0 if self.model_box.count() else -1)
        self.serial_edit.clear()
        self.nickname_edit.clear()
        self.status_box.setCurrentText("NEW")
        self.health_box.setCurrentText("UNKNOWN")
        self.purchase_edit.clear()
        self.opened_edit.clear()
        self.save_button.setText("Register")

    def delete_instance(self):
        if self.current_instance_id is None:
            QMessageBox.information(self, "Info", "Select an instance first.")
            return

        answer = QMessageBox.question(
            self,
            "Confirm",
            f"Retire/delete Motor Instance {self.current_instance_id}?\nHistory is kept by soft delete.",
        )
        if answer != QMessageBox.Yes:
            return

        try:
            self.instance_repo.delete(self.current_instance_id)
            self.clear_form()
            self.load_instances()
        except Exception as exc:
            QMessageBox.critical(self, "Delete Error", str(exc))

    # --------------------------------------------------------
    # Detail / history
    # --------------------------------------------------------
    def open_selected_instance(self, row, _column):
        item = self.instance_table.item(row, 0)
        if item is None:
            return
        instance_id = item.data(Qt.UserRole) or item.text()
        self.load_instance_into_form(instance_id)
        self.show_instance_detail(instance_id)
        self.tabs.setCurrentWidget(self.detail_tab)

    def load_instance_into_form(self, instance_id):
        data = self.instance_repo.get_by_id(instance_id)
        if not data:
            return

        self.current_instance_id = instance_id
        index = self.model_box.findData(data.get("motor_model_id"))
        if index >= 0:
            self.model_box.setCurrentIndex(index)
        self.serial_edit.setText(str(data.get("serial_number") or ""))
        self.nickname_edit.setText(str(data.get("nickname") or ""))
        self.status_box.setCurrentText(str(data.get("status") or "NEW"))
        self.health_box.setCurrentText(str(data.get("health_status") or "UNKNOWN"))
        self.purchase_edit.setText(str(data.get("purchase_date") or ""))
        self.opened_edit.setText(str(data.get("opened_date") or ""))
        self.save_button.setText("Update")

    def show_instance_detail(self, instance_id):
        data = self.instance_repo.get_by_id(instance_id)
        if not data:
            return

        self.current_instance_id = instance_id
        self.detail_title.setText(
            f"Instance {instance_id} — {data.get('nickname') or data.get('serial_number') or ''}"
        )

        fields = [
            ("Instance ID", data.get("instance_id")),
            ("Motor Model ID", data.get("motor_model_id")),
            ("Serial Number", data.get("serial_number")),
            ("Nickname", data.get("nickname")),
            ("Status", data.get("status")),
            ("Health", data.get("health_status")),
            ("Purchase Date", data.get("purchase_date")),
            ("Opened Date", data.get("opened_date")),
            ("Latest Session", data.get("latest_session_id")),
            ("Latest Work", data.get("latest_work_id")),
            ("Anomaly Count", data.get("anomaly_count")),
            ("Consecutive Anomaly", data.get("consecutive_anomaly_count")),
            ("Created", data.get("created_at")),
            ("Updated", data.get("updated_at")),
        ]
        self.detail_info.setRowCount(len(fields))
        for r, (key, value) in enumerate(fields):
            self.detail_info.setItem(r, 0, QTableWidgetItem(key))
            self.detail_info.setItem(r, 1, QTableWidgetItem("" if value is None else str(value)))
        self.detail_info.resizeColumnsToContents()

        try:
            sessions = self.instance_repo.get_session_history(instance_id)
        except Exception:
            sessions = []

        self.history_table.setRowCount(len(sessions))
        for r, session in enumerate(sessions):
            summary = self.instance_repo.get_breakin_summary(session.get("session_id")) or {}
            latest = self.instance_repo.get_latest_log(session.get("session_id")) or {}
            values = [
                session.get("session_id"),
                session.get("device_type"),
                session.get("device_model"),
                session.get("start_datetime"),
                session.get("end_datetime"),
                session.get("result"),
                summary.get("log_count", ""),
                latest.get("measured_rpm", ""),
                latest.get("current_ma", ""),
            ]
            for c, value in enumerate(values):
                self.history_table.setItem(
                    r, c, QTableWidgetItem("" if value is None else str(value))
                )
        self.history_table.resizeColumnsToContents()

    # --------------------------------------------------------
    # Comparison
    # --------------------------------------------------------
    def compare_selected(self):
        rows = sorted({index.row() for index in self.instance_table.selectionModel().selectedRows()})
        if not rows:
            QMessageBox.information(self, "Compare", "Select at least one Motor Instance.")
            return

        instances = []
        for row in rows:
            item = self.instance_table.item(row, 0)
            if item is None:
                continue
            instance_id = item.data(Qt.UserRole) or item.text()
            data = self.instance_repo.get_by_id(instance_id)
            if not data:
                continue

            sessions = self.instance_repo.get_session_history(instance_id)
            latest_session = sessions[0] if sessions else {}
            latest_log = {}
            if latest_session.get("session_id"):
                latest_log = self.instance_repo.get_latest_log(latest_session["session_id"]) or {}

            instances.append((data, latest_session, latest_log))

        headers = ["Metric"] + [str(item[0].get("instance_id")) for item in instances]
        metrics = [
            ("Model", lambda d, s, l: d.get("motor_model_id")),
            ("Nickname", lambda d, s, l: d.get("nickname")),
            ("Status", lambda d, s, l: d.get("status")),
            ("Health", lambda d, s, l: d.get("health_status")),
            ("Latest Session", lambda d, s, l: s.get("session_id")),
            ("Latest Result", lambda d, s, l: s.get("result")),
            ("Latest RPM", lambda d, s, l: l.get("measured_rpm")),
            ("Latest Current mA", lambda d, s, l: l.get("current_ma")),
            ("Latest Voltage V", lambda d, s, l: l.get("voltage_v")),
            ("Latest Temperature C", lambda d, s, l: l.get("temperature_c")),
            ("Latest PWM", lambda d, s, l: l.get("pwm")),
            ("Anomaly Count", lambda d, s, l: d.get("anomaly_count")),
        ]

        self.compare_table.setColumnCount(len(headers))
        self.compare_table.setRowCount(len(metrics))
        self.compare_table.setHorizontalHeaderLabels(headers)

        for r, (name, getter) in enumerate(metrics):
            self.compare_table.setItem(r, 0, QTableWidgetItem(name))
            for c, item in enumerate(instances, start=1):
                value = getter(*item)
                self.compare_table.setItem(
                    r, c, QTableWidgetItem("" if value is None else str(value))
                )

        self.compare_table.resizeColumnsToContents()
        self.tabs.setCurrentWidget(self.compare_tab)

    def closeEvent(self, event):
        self.db.close()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MotorManagerUI()
    window.show()
    sys.exit(app.exec_())
