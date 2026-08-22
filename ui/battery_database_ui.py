"""Operator UI for Battery Model, Instance and confirmed Benchmark registration."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from PyQt5.QtWidgets import (QComboBox, QDialog, QFormLayout, QGroupBox, QLabel,
    QLineEdit, QMessageBox, QPushButton, QDoubleSpinBox, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget, QListWidget)
from battery_system.manual_result_registration import validate_manual_registration, ManualRegistrationError

class BatteryDatabaseDialog(QDialog):
    def __init__(self, db_path: str | Path, parent=None):
        super().__init__(parent); self.db_path=str(db_path); self.setWindowTitle("BATTERY DATABASE / MODEL / INSTANCE / MANUAL REGISTRATION"); self.resize(760,620)
        self._ensure_schema(); self._build(); self.refresh_all(); self.raise_(); self.activateWindow()
    def _db(self): return sqlite3.connect(self.db_path)
    def _ensure_schema(self):
        schema=Path(__file__).resolve().parent.parent/"database/schema/battery_tables.sql"
        with self._db() as db: db.executescript(schema.read_text(encoding="utf-8")); db.commit()
    def _build(self):
        root=QVBoxLayout(self); tabs=QTabWidget(); root.addWidget(tabs)
        page=QWidget(); form=QFormLayout(page); self.model_code=QLineEdit(); self.model_name=QLineEdit(); self.model_chemistry=QLineEdit("NiMH"); self.model_voltage=self._num(0,100,3); self.model_capacity=self._num(0,1000000,1); self.model_manufacturer=QLineEdit(); self.model_notes=QLineEdit()
        for label,w in (("Model Code",self.model_code),("Model Name",self.model_name),("Chemistry",self.model_chemistry),("Nominal Voltage (V)",self.model_voltage),("Nominal Capacity (mAh)",self.model_capacity),("Manufacturer",self.model_manufacturer),("Notes",self.model_notes)): form.addRow(label,w)
        b=QPushButton("REGISTER BATTERY MODEL"); b.clicked.connect(self._register_model); form.addRow(b); self.model_list=QListWidget(); form.addRow("Registered Models",self.model_list); tabs.addTab(page,"1. BATTERY MODEL")
        page=QWidget(); form=QFormLayout(page); self.model=QComboBox(); self.iid=QLineEdit(); self.serial=QLineEdit(); self.nickname=QLineEdit(); self.notes=QLineEdit(); self.status_combo=QComboBox(); self.status_combo.addItems(["NEW","ACTIVE","RETIRED","ARCHIVED"])
        for label,w in (("Battery Model",self.model),("Instance ID",self.iid),("Serial Number",self.serial),("Nickname",self.nickname),("Lifecycle Status",self.status_combo),("Notes",self.notes)): form.addRow(label,w)
        b=QPushButton("REGISTER / UPDATE BATTERY INSTANCE"); b.clicked.connect(self._register_instance); form.addRow(b)
        self.instance_list=QListWidget(); self.instance_list.itemDoubleClicked.connect(lambda item:self._load_instance_into_form(item.data(32))); form.addRow("Registered Battery Instances",self.instance_list); tabs.addTab(page,"2. BATTERY INSTANCE")
        page=QWidget(); layout=QVBoxLayout(page); form=QFormLayout(); self.session=QComboBox(); self.session.setEditable(True); self.result_instance=QComboBox(); self.version=QLineEdit("battery-benchmark-v1"); self.count=QSpinBox(); self.count.setRange(0,100000000); self.avg_v=self._num(0,10,4); self.avg_i=self._num(0,100,4); self.avg_p=self._num(0,1000,4); self.max_i=self._num(0,100,4); self.max_p=self._num(0,1000,4); self.duration=self._num(0,1000000,2); self.drop=self._num(-10,10,4); self.cap=self._num(0,100000,3); self.energy=self._num(0,100000,3)
        fields=(("Session",self.session),("Battery Instance",self.result_instance),("Analysis Version",self.version),("Measurement Count",self.count),("Average Voltage (V)",self.avg_v),("Average Current (A)",self.avg_i),("Average Power (W)",self.avg_p),("Max Current (A)",self.max_i),("Max Power (W)",self.max_p),("Discharge Time (s)",self.duration),("Voltage Drop (V)",self.drop),("Capacity (mAh)",self.cap),("Energy (Wh)",self.energy))
        for label,w in fields: form.addRow(label,w)
        layout.addLayout(form); confirm=QGroupBox("CONFIRMATION"); cl=QVBoxLayout(confirm); self.quality=QPushButton("Measurement quality: NOT CONFIRMED"); self.quality.setCheckable(True); self.quality.clicked.connect(lambda c:self.quality.setText("Measurement quality: OK" if c else "Measurement quality: NOT CONFIRMED")); self.operator=QPushButton("Operator confirmation: NOT CONFIRMED"); self.operator.setCheckable(True); self.operator.clicked.connect(lambda c:self.operator.setText("Operator confirmation: CONFIRMED" if c else "Operator confirmation: NOT CONFIRMED")); cl.addWidget(self.quality); cl.addWidget(self.operator); layout.addWidget(confirm); b=QPushButton("REGISTER CONFIRMED BENCHMARK RESULT"); b.clicked.connect(self._register_result); layout.addWidget(b); self.status=QLabel("Not registered"); layout.addWidget(self.status); tabs.addTab(page,"3. BENCHMARK RESULT")
    @staticmethod
    def _num(a,b,dec): w=QDoubleSpinBox(); w.setRange(a,b); w.setDecimals(dec); return w
    def _load_models(self):
        self.model.clear(); self.model_list.clear()
        with self._db() as db: rows=db.execute("SELECT battery_model_id,model_code,name FROM battery_model WHERE COALESCE(is_deleted,0)=0 ORDER BY model_code").fetchall()
        for mid,code,name in rows: self.model.addItem(f"{code} / {name}",mid); self.model_list.addItem(f"{code} / {name} (ID {mid})")
    def _register_model(self):
        code=self.model_code.text().strip(); name=self.model_name.text().strip()
        if not code or not name: QMessageBox.warning(self,"Battery Model","Model CodeとModel Nameを指定してください。"); return
        try:
            with self._db() as db: db.execute("INSERT INTO battery_model(model_code,name,chemistry,nominal_voltage,capacity_nominal_mah,manufacturer,notes) VALUES(?,?,?,?,?,?,?)",(code,name,self.model_chemistry.text().strip() or None,self.model_voltage.value() or None,self.model_capacity.value() or None,self.model_manufacturer.text().strip() or None,self.model_notes.text().strip() or None)); db.commit()
            self._load_models(); QMessageBox.information(self,"Battery Model",f"{code} を登録しました。")
        except sqlite3.Error as exc: QMessageBox.critical(self,"Battery Model",f"登録できません。\n{exc}")
    def _load_instances(self):
        self.result_instance.clear(); self.instance_list.clear(); self.model.clear()
        with self._db() as db:
            models=db.execute("SELECT battery_model_id,model_code,name FROM battery_model WHERE COALESCE(is_deleted,0)=0 ORDER BY model_code").fetchall(); rows=db.execute("SELECT bi.instance_id,bi.serial_number,bi.nickname,bm.model_code,COALESCE(bi.lifecycle_status,'ACTIVE') FROM battery_instance bi LEFT JOIN battery_model bm ON bm.battery_model_id=bi.battery_model_id WHERE COALESCE(bi.is_deleted,0)=0 ORDER BY bi.instance_id").fetchall()
        for mid,code,name in models: self.model.addItem(f"{code} / {name}",mid)
        for iid,serial,nickname,code,status in rows:
            text=f"{iid} | {code or '-'} | {nickname or '-'} | SN:{serial or '-'} | {status}"; self.result_instance.addItem(text,iid); self.instance_list.addItem(text); self.instance_list.item(self.instance_list.count()-1).setData(32,iid)
    def _load_instance_into_form(self, iid):
        if not iid: return
        with self._db() as db: row=db.execute("SELECT battery_model_id,serial_number,nickname,notes,COALESCE(lifecycle_status,'ACTIVE') FROM battery_instance WHERE instance_id=?",(iid,)).fetchone()
        if not row: return
        mid,serial,nickname,notes,status=row; self.iid.setText(iid); self.iid.setReadOnly(True); idx=self.model.findData(mid); self.model.setCurrentIndex(idx); self.serial.setText(serial or ''); self.nickname.setText(nickname or ''); self.notes.setText(notes or ''); self.status_combo.setCurrentText(status)
    def _register_instance(self):
        iid=self.iid.text().strip()
        if not iid or self.model.currentData() is None: QMessageBox.warning(self,"Battery Instance","Instance IDとBattery Modelを指定してください。"); return
        try:
            with self._db() as db:
                exists=db.execute("SELECT 1 FROM battery_instance WHERE instance_id=?",(iid,)).fetchone()
                if exists:
                    db.execute("UPDATE battery_instance SET battery_model_id=?,serial_number=?,nickname=?,notes=?,lifecycle_status=?,is_deleted=?,updated_at=CURRENT_TIMESTAMP WHERE instance_id=?",(self.model.currentData(),self.serial.text().strip() or None,self.nickname.text().strip() or None,self.notes.text().strip() or None,self.status_combo.currentText(),0 if self.status_combo.currentText()!='ARCHIVED' else 1,iid))
                else:
                    db.execute("INSERT INTO battery_instance(instance_id,battery_model_id,serial_number,nickname,notes,lifecycle_status) VALUES(?,?,?,?,?,?)",(iid,self.model.currentData(),self.serial.text().strip() or None,self.nickname.text().strip() or None,self.notes.text().strip() or None,self.status_combo.currentText()))
                db.commit()
            self._load_instances(); QMessageBox.information(self,"Battery Instance",f"{iid} を保存しました。")
        except sqlite3.Error as exc: QMessageBox.critical(self,"Battery Instance",f"保存できません。\n{exc}")
    def _load_sessions(self):
        self.session.clear()
        with self._db() as db:
            cols={r[1] for r in db.execute("PRAGMA table_info(measurement_session)").fetchall()}
            if 'status' in cols:
                rows=db.execute("SELECT session_id FROM measurement_session WHERE status='COMPLETE' ORDER BY start_time DESC").fetchall()
            else:
                rows=db.execute("SELECT session_id FROM measurement_session WHERE end_time IS NOT NULL ORDER BY end_time DESC").fetchall()
        for (sid,) in rows: self.session.addItem(str(sid),sid)
    def _register_result(self):
        sid=self.session.currentData() or self.session.currentText().strip(); iid=self.result_instance.currentData()
        if not sid or not iid: QMessageBox.warning(self,"Benchmark Result","SessionとBattery Instanceを指定してください。"); return
        try:
            with self._db() as db:
                cols={r[1] for r in db.execute("PRAGMA table_info(measurement_session)").fetchall()}
                row=db.execute("SELECT status FROM measurement_session WHERE session_id=?",(sid,)).fetchone() if 'status' in cols else db.execute("SELECT end_time FROM measurement_session WHERE session_id=?",(sid,)).fetchone()
            if not row: raise ManualRegistrationError("SessionがDBに存在しません")
            session_result=row[0] if 'status' in cols else ('COMPLETE' if row[0] else 'RUNNING')
            validate_manual_registration(session_result=session_result,quality_ok=self.quality.isChecked(),operator_confirmed=self.operator.isChecked())
            values=(sid,iid,self.version.text().strip() or "battery-benchmark-v1",self.count.value(),self.avg_v.value(),self.avg_i.value(),self.avg_p.value(),self.max_i.value(),self.max_p.value(),self.duration.value(),self.drop.value(),self.cap.value(),self.energy.value())
            with self._db() as db: db.execute("INSERT OR REPLACE INTO battery_benchmark_result (session_id,instance_id,analysis_version,measurement_count,avg_voltage,avg_current,avg_power,max_current,max_power,discharge_time_s,voltage_drop,capacity_mah,energy_wh) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",values); db.commit()
            self.status.setText(f"REGISTERED: {sid} / {iid}"); QMessageBox.information(self,"Benchmark Result","正式Benchmark Resultとして登録しました。")
        except (ManualRegistrationError,sqlite3.Error) as exc: QMessageBox.critical(self,"Benchmark Result",str(exc))
    def refresh_all(self): self._load_models(); self._load_instances(); self._load_sessions()
