"""Battery Database / Instance Manager.

The Instance workflow intentionally mirrors the Motor Instance Manager:
model selection, instance list, edit/update, lifecycle status and history/result
registration are separated. Measurement data remains the source of truth.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

from PyQt5.QtWidgets import (
    QComboBox, QDialog, QFormLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QDoubleSpinBox, QSpinBox,
    QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from battery_system.manual_result_registration import (
    validate_manual_registration, ManualRegistrationError,
)


class BatteryDatabaseDialog(QDialog):
    def __init__(self, db_path: str | Path, parent=None):
        super().__init__(parent)
        self.db_path = str(db_path)
        self.current_instance_id = None
        self.setWindowTitle("BATTERY DATABASE / INSTANCE MANAGER")
        self.resize(980, 700)
        self._ensure_schema()
        self._build()
        self.refresh_all()
        self.raise_()
        self.activateWindow()

    def _db(self):
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self):
        schema = Path(__file__).resolve().parent.parent / "database/schema/battery_tables.sql"
        with self._db() as db:
            try:
                db.executescript(schema.read_text(encoding="utf-8"))
            except sqlite3.OperationalError as exc:
                # The additive schema contains an ALTER for older databases.
                # If the column already exists, the CREATE/INSERT portions have
                # still been applied; do not prevent the database UI from opening.
                if "duplicate column name: lifecycle_status" not in str(exc):
                    raise
            db.commit()

    @staticmethod
    def _num(a, b, dec):
        w = QDoubleSpinBox()
        w.setRange(a, b)
        w.setDecimals(dec)
        return w

    def _build(self):
        root = QVBoxLayout(self)
        tabs = QTabWidget()
        root.addWidget(tabs)

        # ---------------- Model ----------------
        page = QWidget(); form = QFormLayout(page)
        self.model_code = QLineEdit(); self.model_name = QLineEdit()
        self.model_chemistry = QLineEdit("NiMH")
        self.model_voltage = self._num(0, 100, 3)
        self.model_capacity = self._num(0, 1000000, 1)
        self.model_manufacturer = QLineEdit(); self.model_notes = QLineEdit()
        for label, widget in (
            ("Model Code", self.model_code), ("Model Name", self.model_name),
            ("Chemistry", self.model_chemistry), ("Nominal Voltage (V)", self.model_voltage),
            ("Nominal Capacity (mAh)", self.model_capacity),
            ("Manufacturer", self.model_manufacturer), ("Notes", self.model_notes),
        ):
            form.addRow(label, widget)
        register_model = QPushButton("REGISTER BATTERY MODEL")
        register_model.clicked.connect(self._register_model)
        form.addRow(register_model)
        self.model_list = QTableWidget(0, 5)
        self.model_list.setHorizontalHeaderLabels(["ID", "Code", "Name", "Chemistry", "Nominal Capacity (mAh)"])
        self.model_list.setEditTriggers(QTableWidget.NoEditTriggers)
        form.addRow(self.model_list)
        tabs.addTab(page, "1. BATTERY MODEL")

        # ---------------- Instance ----------------
        page = QWidget(); layout = QVBoxLayout(page)
        box = QGroupBox("Battery Instance")
        form = QFormLayout(box)
        self.model = QComboBox()
        self.iid = QLineEdit()
        self.iid.setPlaceholderText("BAT0001")
        self.serial = QLineEdit(); self.nickname = QLineEdit(); self.notes = QLineEdit()
        self.lifecycle = QComboBox()
        self.lifecycle.addItems(["NEW", "ACTIVE", "RETIRED", "ARCHIVED"])
        for label, widget in (
            ("Battery Model", self.model), ("Instance ID", self.iid),
            ("Serial Number", self.serial), ("Nickname", self.nickname),
            ("Lifecycle Status", self.lifecycle), ("Notes", self.notes),
        ):
            form.addRow(label, widget)
        layout.addWidget(box)

        buttons = QHBoxLayout()
        self.instance_save = QPushButton("REGISTER / UPDATE")
        self.instance_save.clicked.connect(self._save_instance)
        new_button = QPushButton("NEW")
        new_button.clicked.connect(self._clear_instance_form)
        retire_button = QPushButton("RETIRE")
        retire_button.clicked.connect(self._retire_instance)
        restore_button = QPushButton("RESTORE ACTIVE")
        restore_button.clicked.connect(self._restore_instance)
        for button in (self.instance_save, new_button, retire_button, restore_button):
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.instance_table = QTableWidget(0, 7)
        self.instance_table.setHorizontalHeaderLabels(
            ["ID", "Model", "Serial", "Nickname", "Status", "Created", "Updated"]
        )
        self.instance_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.instance_table.setSelectionMode(QTableWidget.SingleSelection)
        self.instance_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.instance_table.cellDoubleClicked.connect(self._open_instance)
        self.instance_table.itemSelectionChanged.connect(self._selection_changed)
        layout.addWidget(self.instance_table)
        layout.addWidget(QLabel("Double-click an instance to edit it. History is retained when an instance is retired."))
        tabs.addTab(page, "2. BATTERY INSTANCE")

        # ---------------- Benchmark result ----------------
        page = QWidget(); layout = QVBoxLayout(page); form = QFormLayout()
        self.session = QComboBox(); self.session.setEditable(True)
        self.result_instance = QComboBox(); self.version = QLineEdit("battery-benchmark-v1")
        self.count = QSpinBox(); self.count.setRange(0, 100000000)
        self.avg_v = self._num(0, 10, 4); self.avg_i = self._num(0, 100, 4)
        self.avg_p = self._num(0, 1000, 4); self.max_i = self._num(0, 100, 4)
        self.max_p = self._num(0, 1000, 4); self.duration = self._num(0, 1000000, 2)
        self.drop = self._num(-10, 10, 4); self.cap = self._num(0, 100000, 3); self.energy = self._num(0, 100000, 3)
        fields = (
            ("Session", self.session), ("Battery Instance", self.result_instance),
            ("Analysis Version", self.version), ("Measurement Count", self.count),
            ("Average Voltage (V)", self.avg_v), ("Average Current (A)", self.avg_i),
            ("Average Power (W)", self.avg_p), ("Max Current (A)", self.max_i),
            ("Max Power (W)", self.max_p), ("Discharge Time (s)", self.duration),
            ("Voltage Drop (V)", self.drop), ("Capacity (mAh)", self.cap),
            ("Energy (Wh)", self.energy),
        )
        for label, widget in fields: form.addRow(label, widget)
        layout.addLayout(form)
        confirm = QGroupBox("CONFIRMATION"); cl = QVBoxLayout(confirm)
        self.quality = QPushButton("Measurement quality: NOT CONFIRMED"); self.quality.setCheckable(True)
        self.operator = QPushButton("Operator confirmation: NOT CONFIRMED"); self.operator.setCheckable(True)
        self.quality.clicked.connect(lambda checked: self.quality.setText("Measurement quality: OK" if checked else "Measurement quality: NOT CONFIRMED"))
        self.operator.clicked.connect(lambda checked: self.operator.setText("Operator confirmation: CONFIRMED" if checked else "Operator confirmation: NOT CONFIRMED"))
        cl.addWidget(self.quality); cl.addWidget(self.operator); layout.addWidget(confirm)
        register_result = QPushButton("REGISTER CONFIRMED BENCHMARK RESULT")
        register_result.clicked.connect(self._register_result)
        layout.addWidget(register_result)
        self.status = QLabel("Not registered"); layout.addWidget(self.status)
        tabs.addTab(page, "3. BENCHMARK RESULT")

    # ---------- Model ----------
    def _load_models(self):
        self.model.blockSignals(True); self.model.clear(); self.model.blockSignals(False)
        self.model_list.setRowCount(0)
        with self._db() as db:
            rows = db.execute(
                "SELECT battery_model_id,model_code,name,chemistry,capacity_nominal_mah "
                "FROM battery_model WHERE COALESCE(is_deleted,0)=0 ORDER BY model_code"
            ).fetchall()
        for row in rows:
            mid, code, name, chemistry, capacity = row
            self.model.addItem(f"{code} / {name}", mid)
            r = self.model_list.rowCount(); self.model_list.insertRow(r)
            for c, value in enumerate(row): self.model_list.setItem(r, c, QTableWidgetItem("" if value is None else str(value)))
        self.model_list.resizeColumnsToContents()

    def _register_model(self):
        code = self.model_code.text().strip(); name = self.model_name.text().strip()
        if not code or not name:
            QMessageBox.warning(self, "Battery Model", "Model CodeとModel Nameを指定してください。"); return
        try:
            with self._db() as db:
                db.execute(
                    "INSERT INTO battery_model(model_code,name,chemistry,nominal_voltage,capacity_nominal_mah,manufacturer,notes) VALUES(?,?,?,?,?,?,?)",
                    (code, name, self.model_chemistry.text().strip() or None, self.model_voltage.value() or None,
                     self.model_capacity.value() or None, self.model_manufacturer.text().strip() or None,
                     self.model_notes.text().strip() or None))
                db.commit()
            self._load_models(); QMessageBox.information(self, "Battery Model", f"{code} を登録しました。")
        except sqlite3.Error as exc:
            QMessageBox.critical(self, "Battery Model", f"登録できません。\n{exc}")

    # ---------- Instance ----------
    def _load_instances(self):
        current = self.model.currentData()
        self.instance_table.setRowCount(0); self.result_instance.clear()
        with self._db() as db:
            rows = db.execute(
                "SELECT bi.instance_id,bi.battery_model_id,bi.serial_number,bi.nickname,"
                "bi.lifecycle_status,bi.created_at,bi.updated_at,bm.model_code "
                "FROM battery_instance bi LEFT JOIN battery_model bm ON bm.battery_model_id=bi.battery_model_id "
                "WHERE COALESCE(bi.is_deleted,0)=0 ORDER BY bi.instance_id"
            ).fetchall()
        for iid, mid, serial, nickname, status, created, updated, code in rows:
            r = self.instance_table.rowCount(); self.instance_table.insertRow(r)
            values = [iid, code or "-", serial or "-", nickname or "-", status or "ACTIVE", created or "", updated or ""]
            for c, value in enumerate(values):
                item = QTableWidgetItem(str(value));
                if c == 0: item.setData(32, iid)
                self.instance_table.setItem(r, c, item)
            if status == "RETIRED":
                for c in range(self.instance_table.columnCount()): self.instance_table.item(r, c).setToolTip("RETIRED: new measurements must not use this instance")
            if status in ("ACTIVE", "NEW"):
                self.result_instance.addItem(f"{iid} / {code or '-'}", iid)
        self.instance_table.resizeColumnsToContents()
        if current is not None:
            idx = self.model.findData(current)
            if idx >= 0: self.model.setCurrentIndex(idx)

    def _selection_changed(self):
        rows = self.instance_table.selectionModel().selectedRows()
        if rows: self._load_instance_into_form(self.instance_table.item(rows[0].row(), 0).text())

    def _open_instance(self, row, _column):
        self._load_instance_into_form(self.instance_table.item(row, 0).text())

    def _load_instance_into_form(self, instance_id):
        with self._db() as db:
            row = db.execute(
                "SELECT instance_id,battery_model_id,serial_number,nickname,notes,lifecycle_status "
                "FROM battery_instance WHERE instance_id=?", (instance_id,)
            ).fetchone()
        if not row: return
        iid, mid, serial, nickname, notes, lifecycle = row
        self.current_instance_id = iid
        idx = self.model.findData(mid)
        if idx >= 0: self.model.setCurrentIndex(idx)
        self.iid.setText(str(iid)); self.iid.setReadOnly(True)
        self.serial.setText(serial or ""); self.nickname.setText(nickname or ""); self.notes.setText(notes or "")
        self.lifecycle.setCurrentText(lifecycle or "ACTIVE")
        self.instance_save.setText("UPDATE")

    def _clear_instance_form(self):
        self.current_instance_id = None; self.iid.setReadOnly(False); self.iid.clear()
        self.serial.clear(); self.nickname.clear(); self.notes.clear(); self.lifecycle.setCurrentText("NEW")
        if self.model.count(): self.model.setCurrentIndex(0)
        self.instance_save.setText("REGISTER")
        self.instance_table.clearSelection()

    def _save_instance(self):
        iid = self.iid.text().strip(); mid = self.model.currentData()
        if not iid or mid is None:
            QMessageBox.warning(self, "Battery Instance", "Instance IDとBattery Modelを指定してください。"); return
        try:
            with self._db() as db:
                if self.current_instance_id is None:
                    db.execute(
                        "INSERT INTO battery_instance(instance_id,battery_model_id,serial_number,nickname,notes,lifecycle_status) VALUES(?,?,?,?,?,?)",
                        (iid, mid, self.serial.text().strip() or None, self.nickname.text().strip() or None,
                         self.notes.text().strip() or None, self.lifecycle.currentText()))
                else:
                    db.execute(
                        "UPDATE battery_instance SET battery_model_id=?,serial_number=?,nickname=?,notes=?,lifecycle_status=?,updated_at=CURRENT_TIMESTAMP WHERE instance_id=?",
                        (mid, self.serial.text().strip() or None, self.nickname.text().strip() or None,
                         self.notes.text().strip() or None, self.lifecycle.currentText(), self.current_instance_id))
                db.commit()
            self._load_instances(); QMessageBox.information(self, "Battery Instance", f"{iid} を保存しました。")
        except sqlite3.Error as exc:
            QMessageBox.critical(self, "Battery Instance", f"保存できません。\n{exc}")

    def _retire_instance(self):
        if not self.current_instance_id:
            QMessageBox.information(self, "Battery Instance", "引退するInstanceを選択してください。"); return
        if QMessageBox.question(self, "Retire", f"{self.current_instance_id} を引退にしますか？\n過去の履歴は保持されます。") != QMessageBox.Yes: return
        with self._db() as db:
            db.execute("UPDATE battery_instance SET lifecycle_status='RETIRED',updated_at=CURRENT_TIMESTAMP WHERE instance_id=?", (self.current_instance_id,)); db.commit()
        self._load_instances(); self._load_instance_into_form(self.current_instance_id)

    def _restore_instance(self):
        if not self.current_instance_id:
            QMessageBox.information(self, "Battery Instance", "復帰するInstanceを選択してください。"); return
        with self._db() as db:
            db.execute("UPDATE battery_instance SET lifecycle_status='ACTIVE',is_deleted=0,updated_at=CURRENT_TIMESTAMP WHERE instance_id=?", (self.current_instance_id,)); db.commit()
        self._load_instances(); self._load_instance_into_form(self.current_instance_id)

    # ---------- Result ----------
    def _load_sessions(self):
        self.session.clear()
        with self._db() as db:
            rows = db.execute("SELECT session_id FROM measurement_session WHERE status='COMPLETE' ORDER BY start_time DESC").fetchall()
        for (sid,) in rows: self.session.addItem(str(sid), sid)

    def _register_result(self):
        sid = self.session.currentData() or self.session.currentText().strip(); iid = self.result_instance.currentData()
        if not sid or not iid:
            QMessageBox.warning(self, "Benchmark Result", "SessionとBattery Instanceを指定してください。"); return
        try:
            with self._db() as db: row = db.execute("SELECT status FROM measurement_session WHERE session_id=?", (sid,)).fetchone()
            if not row: raise ManualRegistrationError("SessionがDBに存在しません")
            validate_manual_registration(session_result=row[0], quality_ok=self.quality.isChecked(), operator_confirmed=self.operator.isChecked())
            values = (sid, iid, self.version.text().strip() or "battery-benchmark-v1", self.count.value(), self.avg_v.value(), self.avg_i.value(), self.avg_p.value(), self.max_i.value(), self.max_p.value(), self.duration.value(), self.drop.value(), self.cap.value(), self.energy.value())
            with self._db() as db:
                db.execute(
                    "INSERT OR REPLACE INTO battery_benchmark_result "
                    "(session_id,instance_id,analysis_version,measurement_count,avg_voltage,avg_current,avg_power,max_current,max_power,discharge_time_s,voltage_drop,capacity_mah,energy_wh) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)", values)
                db.commit()
            self.status.setText(f"REGISTERED: {sid} / {iid}"); QMessageBox.information(self, "Benchmark Result", "正式Benchmark Resultとして登録しました。")
        except (ManualRegistrationError, sqlite3.Error) as exc:
            QMessageBox.critical(self, "Benchmark Result", str(exc))

    def refresh_all(self):
        self._load_models(); self._load_instances(); self._load_sessions()
