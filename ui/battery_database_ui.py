"""Minimal operator UI for Battery Instance and confirmed Benchmark registration."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from PyQt5.QtWidgets import QComboBox,QDialog,QFormLayout,QGroupBox,QLabel,QLineEdit,QMessageBox,QPushButton,QDoubleSpinBox,QSpinBox,QTabWidget,QVBoxLayout,QWidget
from battery_system.manual_result_registration import validate_manual_registration,ManualRegistrationError

class BatteryDatabaseDialog(QDialog):
    def __init__(self,db_path: str|Path,parent=None):
        super().__init__(parent); self.db_path=str(db_path); self.setWindowTitle("BATTERY DATABASE / MANUAL REGISTRATION"); self.resize(620,560); self._build(); self._ensure_schema(); self._load_models(); self._load_instances(); self._load_sessions()
    def _db(self): return sqlite3.connect(self.db_path)
    def _ensure_schema(self):
        schema=Path(__file__).resolve().parent.parent/"database/schema/battery_tables.sql"
        with self._db() as d: d.executescript(schema.read_text(encoding="utf-8")); d.commit()
    def _build(self):
        root=QVBoxLayout(self); tabs=QTabWidget(); root.addWidget(tabs); w=QWidget(); f=QFormLayout(w); self.model=QComboBox(); self.iid=QLineEdit(); self.serial=QLineEdit(); self.nickname=QLineEdit(); self.notes=QLineEdit()
        for n,x in (("Battery Model",self.model),("Instance ID",self.iid),("Serial Number",self.serial),("Nickname",self.nickname),("Notes",self.notes)): f.addRow(n,x)
        b=QPushButton("REGISTER BATTERY INSTANCE"); b.clicked.connect(self._register_instance); f.addRow(b); tabs.addTab(w,"1. INSTANCE")
        w=QWidget(); r=QVBoxLayout(w); f=QFormLayout(); self.session=QComboBox(); self.session.setEditable(True); self.instance=QComboBox(); self.version=QLineEdit("battery-benchmark-v1"); self.count=QSpinBox(); self.count.setRange(0,100000000); self.avg_v=self._num(0,10,4); self.avg_i=self._num(0,100,4); self.avg_p=self._num(0,1000,4); self.max_i=self._num(0,100,4); self.max_p=self._num(0,1000,4); self.duration=self._num(0,1000000,2); self.drop=self._num(-10,10,4); self.cap=self._num(0,100000,3); self.energy=self._num(0,100000,3)
        for n,x in (("Session",self.session),("Battery Instance",self.instance),("Analysis Version",self.version),("Measurement Count",self.count),("Average Voltage (V)",self.avg_v),("Average Current (A)",self.avg_i),("Average Power (W)",self.avg_p),("Max Current (A)",self.max_i),("Max Power (W)",self.max_p),("Discharge Time (s)",self.duration),("Voltage Drop (V)",self.drop),("Capacity (mAh)",self.cap),("Energy (Wh)",self.energy)): f.addRow(n,x)
        r.addLayout(f); q=QGroupBox("CONFIRMATION"); ql=QVBoxLayout(q); self.quality=QPushButton("Measurement quality: NOT CONFIRMED"); self.quality.setCheckable(True); self.quality.clicked.connect(lambda c:self.quality.setText("Measurement quality: OK" if c else "Measurement quality: NOT CONFIRMED")); self.operator=QPushButton("Operator confirmation: NOT CONFIRMED"); self.operator.setCheckable(True); self.operator.clicked.connect(lambda c:self.operator.setText("Operator confirmation: CONFIRMED" if c else "Operator confirmation: NOT CONFIRMED")); ql.addWidget(self.quality); ql.addWidget(self.operator); r.addWidget(q); b=QPushButton("REGISTER CONFIRMED BENCHMARK RESULT"); b.clicked.connect(self._register_result); r.addWidget(b); self.status=QLabel("Not registered"); r.addWidget(self.status); tabs.addTab(w,"2. BENCHMARK RESULT")
    @staticmethod
    def _num(a,b,d): x=QDoubleSpinBox(); x.setRange(a,b); x.setDecimals(d); return x
    def _load_models(self):
        self.model.clear()
        with self._db() as d:
            for mid,code,name in d.execute("SELECT battery_model_id,model_code,name FROM battery_model WHERE COALESCE(is_deleted,0)=0 ORDER BY model_code"): self.model.addItem(f"{code} / {name}",mid)
    def _load_instances(self):
        self.instance.clear()
        with self._db() as d:
            for iid,nick in d.execute("SELECT instance_id,nickname FROM battery_instance WHERE COALESCE(is_deleted,0)=0 ORDER BY instance_id"): self.instance.addItem(f"{iid} / {nick or ''}".rstrip(" /"),iid)
    def _load_sessions(self):
        self.session.clear()
        with self._db() as d:
            for (sid,) in d.execute("SELECT session_id FROM measurement_session WHERE result='COMPLETE' ORDER BY start_datetime DESC"): self.session.addItem(sid,sid)
    def _register_instance(self):
        iid=self.iid.text().strip()
        if not iid or self.model.currentData() is None: QMessageBox.warning(self,"Battery Instance","Instance IDとBattery Modelを指定してください。"); return
        try:
            with self._db() as d: d.execute("INSERT INTO battery_instance(instance_id,battery_model_id,serial_number,nickname,notes) VALUES(?,?,?,?,?)",(iid,self.model.currentData(),self.serial.text().strip() or None,self.nickname.text().strip() or None,self.notes.text().strip() or None)); d.commit()
            self._load_instances(); QMessageBox.information(self,"Battery Instance",f"{iid} を登録しました。")
        except sqlite3.IntegrityError as e: QMessageBox.critical(self,"Battery Instance",f"登録できません。\n{e}")
    def _register_result(self):
        sid=self.session.currentData() or self.session.currentText().strip(); iid=self.instance.currentData()
        if not sid or not iid: QMessageBox.warning(self,"Benchmark Result","SessionとBattery Instanceを指定してください。"); return
        try:
            with self._db() as d: row=d.execute("SELECT result FROM measurement_session WHERE session_id=?",(sid,)).fetchone()
            if not row: raise ManualRegistrationError("SessionがDBに存在しません")
            validate_manual_registration(session_result=row[0],quality_ok=self.quality.isChecked(),operator_confirmed=self.operator.isChecked())
            v={"session_id":sid,"instance_id":iid,"analysis_version":self.version.text().strip() or "battery-benchmark-v1","measurement_count":self.count.value(),"avg_voltage":self.avg_v.value(),"avg_current":self.avg_i.value(),"avg_power":self.avg_p.value(),"max_current":self.max_i.value(),"max_power":self.max_p.value(),"discharge_time_s":self.duration.value(),"voltage_drop":self.drop.value(),"capacity_mah":self.cap.value(),"energy_wh":self.energy.value()}; cols=','.join(v); qs=','.join('?' for _ in v)
            with self._db() as d: d.execute(f"INSERT OR REPLACE INTO battery_benchmark_result ({cols}) VALUES ({qs})",tuple(v.values())); d.commit()
            self.status.setText(f"REGISTERED: {sid} / {iid}"); QMessageBox.information(self,"Benchmark Result","正式Benchmark Resultとして登録しました。")
        except (ManualRegistrationError,sqlite3.Error) as e: QMessageBox.critical(self,"Benchmark Result",str(e))
