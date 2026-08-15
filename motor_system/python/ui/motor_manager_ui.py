# ============================================================
# motor_manager_ui.py
# MINI4WD AI SYSTEM - Motor Instance Manager
# Revision 3
# ============================================================

import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QApplication, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton, QTabWidget, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget)

ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(ROOT))

from database.manager.database_manager import DatabaseManager
from database.repository.motor_instance_repository import MotorInstanceRepository
from database.repository.motor_repository import MotorRepository
from database.repository.benchmark_result_repository import BenchmarkResultRepository

class MotorManagerUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Motor Instance Manager")
        self.resize(1180, 760)
        self.db = DatabaseManager(str(ROOT / "database" / "mini4wd.db")); self.db.connect()
        self.motor_repo = MotorRepository(self.db); self.instance_repo = MotorInstanceRepository(self.db); self.benchmark_repo = BenchmarkResultRepository(self.db)
        self.current_instance_id = None
        self.setup_ui(); self.load_models(); self.load_instances()

    def setup_ui(self):
        root = QVBoxLayout(self); header = QHBoxLayout(); title = QLabel("Motor Instance Manager"); title.setStyleSheet("font-size:20px;font-weight:bold;"); header.addWidget(title); header.addStretch(); refresh = QPushButton("Refresh"); refresh.clicked.connect(self.refresh_all); header.addWidget(refresh); root.addLayout(header)
        self.tabs = QTabWidget(); self.instance_tab = QWidget(); self.detail_tab = QWidget(); self.compare_tab = QWidget(); self.tabs.addTab(self.instance_tab,"Instances"); self.tabs.addTab(self.detail_tab,"Detail / History"); self.tabs.addTab(self.compare_tab,"Compare"); root.addWidget(self.tabs); self.setup_instance_tab(); self.setup_detail_tab(); self.setup_compare_tab()

    def setup_instance_tab(self):
        layout = QVBoxLayout(self.instance_tab); box = QGroupBox("Motor Instance"); form = QFormLayout(box)
        self.model_box=QComboBox(); form.addRow("Motor Model",self.model_box); self.serial_edit=QLineEdit(); form.addRow("Serial Number",self.serial_edit); self.nickname_edit=QLineEdit(); form.addRow("Nickname",self.nickname_edit)
        self.status_box=QComboBox(); self.status_box.addItems(["NEW","ACTIVE","MAINTENANCE","RETIRED","ARCHIVED"]); form.addRow("Status",self.status_box); self.health_box=QComboBox(); self.health_box.addItems(["UNKNOWN","GOOD","WARNING","BAD"]); form.addRow("Health",self.health_box)
        self.purchase_edit=QLineEdit(); self.purchase_edit.setPlaceholderText("YYYY-MM-DD"); form.addRow("Purchase Date",self.purchase_edit); self.opened_edit=QLineEdit(); self.opened_edit.setPlaceholderText("YYYY-MM-DD"); form.addRow("Opened Date",self.opened_edit); layout.addWidget(box)
        buttons=QHBoxLayout(); self.save_button=QPushButton("Register"); self.save_button.clicked.connect(self.save_instance); buttons.addWidget(self.save_button); new_button=QPushButton("New"); new_button.clicked.connect(self.clear_form); buttons.addWidget(new_button); delete_button=QPushButton("Retire / Delete"); delete_button.clicked.connect(self.delete_instance); buttons.addWidget(delete_button); buttons.addStretch(); layout.addLayout(buttons)
        self.instance_table=QTableWidget(); self.instance_table.setColumnCount(11); self.instance_table.setHorizontalHeaderLabels(["ID","Model","Serial","Nickname","Status","Health","Latest Session","Benchmark RPM","Anomaly","Created","Updated"]); self.instance_table.setSelectionBehavior(QTableWidget.SelectRows); self.instance_table.setSelectionMode(QTableWidget.ExtendedSelection); self.instance_table.setEditTriggers(QTableWidget.NoEditTriggers); self.instance_table.cellDoubleClicked.connect(self.open_selected_instance); layout.addWidget(self.instance_table); layout.addWidget(QLabel("Double-click an instance to edit/view history. Select multiple rows for comparison."))

    def setup_detail_tab(self):
        layout=QVBoxLayout(self.detail_tab); self.detail_title=QLabel("No instance selected"); self.detail_title.setStyleSheet("font-size:18px;font-weight:bold;"); layout.addWidget(self.detail_title); self.detail_info=QTableWidget(); self.detail_info.setColumnCount(2); self.detail_info.setHorizontalHeaderLabels(["Field","Value"]); self.detail_info.setEditTriggers(QTableWidget.NoEditTriggers); layout.addWidget(self.detail_info); layout.addWidget(QLabel("Measurement / Break-in History")); self.history_table=QTableWidget(); self.history_table.setColumnCount(10); self.history_table.setHorizontalHeaderLabels(["Session","Device","Device Model","Start","End","Result","Logs","Measured RPM","Benchmark RPM","Last Current mA"]); self.history_table.setEditTriggers(QTableWidget.NoEditTriggers); layout.addWidget(self.history_table)

    def setup_compare_tab(self):
        layout=QVBoxLayout(self.compare_tab); row=QHBoxLayout(); row.addWidget(QLabel("Selected Motor Instances")); button=QPushButton("Compare Selected"); button.clicked.connect(self.compare_selected); row.addWidget(button); row.addStretch(); layout.addLayout(row); self.compare_table=QTableWidget(); self.compare_table.setEditTriggers(QTableWidget.NoEditTriggers); layout.addWidget(self.compare_table)

    @staticmethod
    def _model_display_name(model):
        name=model.get("name",model.get("motor_model_id")); code=model.get("model_code"); return f"{name} ({code})" if code else str(name)

    def load_models(self):
        self.model_box.clear()
        for model in self.motor_repo.get_all(): self.model_box.addItem(self._model_display_name(model),model.get("motor_model_id"))

    def load_instances(self):
        try: rows=self.instance_repo.get_list_view()
        except Exception: rows=self.instance_repo.get_all_active()
        self.instance_table.setRowCount(len(rows))
        for r,data in enumerate(rows):
            benchmark=self.instance_repo.get_latest_benchmark(data.get("instance_id")) if self._benchmark_table_available() else None
            model_name=data.get("motor_name"); model_code=data.get("model_code")
            model_display=f"{model_name} ({model_code})" if model_name and model_code else (str(model_name) if model_name else str(data.get("motor_model_id") or ""))
            values=[data.get("instance_id"),model_display,data.get("serial_number"),data.get("nickname"),data.get("status"),data.get("health_status"),data.get("latest_session_id"),benchmark.get("benchmark_rpm") if benchmark else None,data.get("anomaly_count",0),data.get("created_at"),data.get("updated_at")]
            for c,value in enumerate(values):
                item=QTableWidgetItem("" if value is None else str(value));
                if c==0: item.setData(Qt.UserRole,data.get("instance_id"))
                self.instance_table.setItem(r,c,item)
        self.instance_table.resizeColumnsToContents()

    def _benchmark_table_available(self):
        try: return self.db.table_exists("benchmark_result")
        except Exception: return False

    def refresh_all(self): self.load_models(); self.load_instances(); self.show_instance_detail(self.current_instance_id) if self.current_instance_id else None

    def collect_form_data(self):
        model_id=self.model_box.currentData()
        if model_id is None: raise ValueError("Motor Model is required.")
        serial=self.serial_edit.text().strip(); nickname=self.nickname_edit.text().strip()
        if not serial and not nickname: raise ValueError("Serial Number or Nickname is required.")
        return {"motor_model_id":model_id,"serial_number":serial,"nickname":nickname,"status":self.status_box.currentText(),"health_status":self.health_box.currentText(),"purchase_date":self.purchase_edit.text().strip() or None,"opened_date":self.opened_edit.text().strip() or None}

    def supported_instance_data(self,data):
        columns={row[1] for row in self.db.execute("PRAGMA table_info(motor_instance)").fetchall()}; return {key:value for key,value in data.items() if key in columns}

    def save_instance(self):
        try:
            data=self.supported_instance_data(self.collect_form_data()); instance_id=self.instance_repo.create(data) if self.current_instance_id is None else self.current_instance_id
            if self.current_instance_id is not None: self.instance_repo.update_instance(instance_id,data)
            self.current_instance_id=instance_id; self.load_instances(); self.show_instance_detail(instance_id); QMessageBox.information(self,"Complete",f"Motor Instance updated/created: {instance_id}")
        except Exception as exc: QMessageBox.critical(self,"Save Error",str(exc))

    def clear_form(self):
        self.current_instance_id=None; self.model_box.setCurrentIndex(0 if self.model_box.count() else -1)
        for edit in (self.serial_edit,self.nickname_edit,self.purchase_edit,self.opened_edit): edit.clear()
        self.status_box.setCurrentText("NEW"); self.health_box.setCurrentText("UNKNOWN"); self.save_button.setText("Register")

    def delete_instance(self):
        if not self.current_instance_id: QMessageBox.information(self,"Info","Select an instance first."); return
        if QMessageBox.question(self,"Confirm",f"Retire/delete Motor Instance {self.current_instance_id}?\nHistory is kept by soft delete.")!=QMessageBox.Yes:return
        try:self.instance_repo.delete(self.current_instance_id); self.clear_form(); self.load_instances()
        except Exception as exc:QMessageBox.critical(self,"Delete Error",str(exc))

    def open_selected_instance(self,row,_column):
        item=self.instance_table.item(row,0)
        if item is None:return
        instance_id=item.data(Qt.UserRole) or item.text(); self.load_instance_into_form(instance_id); self.show_instance_detail(instance_id); self.tabs.setCurrentWidget(self.detail_tab)

    def load_instance_into_form(self,instance_id):
        data=self.instance_repo.get_by_id(instance_id)
        if not data:return
        self.current_instance_id=instance_id; index=self.model_box.findData(data.get("motor_model_id"));
        if index>=0:self.model_box.setCurrentIndex(index)
        self.serial_edit.setText(str(data.get("serial_number") or "")); self.nickname_edit.setText(str(data.get("nickname") or "")); self.status_box.setCurrentText(str(data.get("status") or "NEW")); self.health_box.setCurrentText(str(data.get("health_status") or "UNKNOWN")); self.purchase_edit.setText(str(data.get("purchase_date") or "")); self.opened_edit.setText(str(data.get("opened_date") or "")); self.save_button.setText("Update")

    def show_instance_detail(self,instance_id):
        data=self.instance_repo.get_by_id(instance_id)
        if not data:return
        self.current_instance_id=instance_id; self.detail_title.setText(f"Instance {instance_id} — {data.get('nickname') or data.get('serial_number') or ''}")
        latest_benchmark=self.instance_repo.get_latest_benchmark(instance_id) if self._benchmark_table_available() else None; fields=[("Instance ID",data.get("instance_id")),("Motor Model ID",data.get("motor_model_id")),("Serial Number",data.get("serial_number")),("Nickname",data.get("nickname")),("Status",data.get("status")),("Health",data.get("health_status")),("Purchase Date",data.get("purchase_date")),("Opened Date",data.get("opened_date")),("Latest Session",data.get("latest_session_id")),("Latest Benchmark RPM",latest_benchmark.get("benchmark_rpm") if latest_benchmark else None),("Anomaly Count",data.get("anomaly_count")),("Consecutive Anomaly",data.get("consecutive_anomaly_count")),("Created",data.get("created_at")),("Updated",data.get("updated_at"))]
        self.detail_info.setRowCount(len(fields))
        for r,(key,value) in enumerate(fields):self.detail_info.setItem(r,0,QTableWidgetItem(key));self.detail_info.setItem(r,1,QTableWidgetItem("" if value is None else str(value)))
        self.detail_info.resizeColumnsToContents()
        try:sessions=self.instance_repo.get_session_history(instance_id)
        except Exception:sessions=[]
        self.history_table.setRowCount(len(sessions))
        for r,session in enumerate(sessions):
            summary=self.instance_repo.get_breakin_summary(session.get("session_id")) or {}; latest=self.instance_repo.get_latest_log(session.get("session_id")) or {}; benchmark=self.benchmark_repo.get_by_session(session.get("session_id")) if self._benchmark_table_available() else None; values=[session.get("session_id"),session.get("device_type"),session.get("device_model"),session.get("start_datetime"),session.get("end_datetime"),session.get("result"),summary.get("log_count",""),latest.get("measured_rpm",""),benchmark.get("benchmark_rpm") if benchmark else None,latest.get("current_ma","")]
            for c,value in enumerate(values):self.history_table.setItem(r,c,QTableWidgetItem("" if value is None else str(value)))
        self.history_table.resizeColumnsToContents()

    def compare_selected(self):
        rows=sorted({index.row() for index in self.instance_table.selectionModel().selectedRows()})
        if not rows:QMessageBox.information(self,"Compare","Select at least one Motor Instance.");return
        instances=[]
        for row in rows:
            item=self.instance_table.item(row,0)
            if item is None:continue
            instance_id=item.data(Qt.UserRole) or item.text(); data=self.instance_repo.get_by_id(instance_id)
            if not data:continue
            sessions=self.instance_repo.get_session_history(instance_id); session=sessions[0] if sessions else {}; log=self.instance_repo.get_latest_log(session.get("session_id")) if session.get("session_id") else {}; benchmark=self.instance_repo.get_latest_benchmark(instance_id) if self._benchmark_table_available() else None; instances.append((data,session,log or {},benchmark or {}))
        headers=["Metric"]+[str(x[0].get("instance_id")) for x in instances]; metrics=[("Model",lambda d,s,l,b:d.get("motor_model_id")),("Nickname",lambda d,s,l,b:d.get("nickname")),("Status",lambda d,s,l,b:d.get("status")),("Health",lambda d,s,l,b:d.get("health_status")),("Latest Session",lambda d,s,l,b:s.get("session_id")),("Latest Result",lambda d,s,l,b:s.get("result")),("Measured RPM",lambda d,s,l,b:l.get("measured_rpm")),("Benchmark RPM",lambda d,s,l,b:b.get("benchmark_rpm")),("Current mA",lambda d,s,l,b:l.get("current_ma")),("Voltage V",lambda d,s,l,b:l.get("voltage_v")),("Temperature C",lambda d,s,l,b:l.get("temperature_c")),("PWM",lambda d,s,l,b:l.get("pwm")),("Anomaly Count",lambda d,s,l,b:d.get("anomaly_count"))]
        self.compare_table.setColumnCount(len(headers));self.compare_table.setRowCount(len(metrics));self.compare_table.setHorizontalHeaderLabels(headers)
        for r,(name,getter) in enumerate(metrics):
            self.compare_table.setItem(r,0,QTableWidgetItem(name))
            for c,instance in enumerate(instances,start=1):value=getter(*instance);self.compare_table.setItem(r,c,QTableWidgetItem("" if value is None else str(value)))
        self.compare_table.resizeColumnsToContents();self.tabs.setCurrentWidget(self.compare_tab)

    def closeEvent(self,event):self.db.close();event.accept()

if __name__=="__main__":
    app=QApplication(sys.argv);window=MotorManagerUI();window.show();sys.exit(app.exec_())
