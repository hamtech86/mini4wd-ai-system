"""Operator UI for Battery Model, Instance and confirmed Benchmark registration."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from PyQt5.QtWidgets import (QComboBox, QDialog, QFormLayout, QGroupBox, QLabel,
    QLineEdit, QMessageBox, QPushButton, QDoubleSpinBox, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget, QListWidget, QHBoxLayout)
from battery_system.manual_result_registration import validate_manual_registration, ManualRegistrationError


class BatteryDatabaseDialog(QDialog):
    def __init__(self, db_path: str | Path, parent=None):
        super().__init__(parent)
        self.db_path = str(db_path)
        self.setWindowTitle("BATTERY DATABASE / MODEL / INSTANCE / MANUAL REGISTRATION")
        self.resize(900, 700)
        self._ensure_schema()
        self._build()
        self.refresh_all()
        self.raise_(); self.activateWindow()

    def _db(self):
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self):
        schema = Path(__file__).resolve().parent.parent / "database/schema/battery_tables.sql"
        with self._db() as db:
            db.executescript(schema.read_text(encoding="utf-8"))
            db.commit()

    def _build(self):
        root = QVBoxLayout(self)
        tabs = QTabWidget(); root.addWidget(tabs)

        page = QWidget(); form = QFormLayout(page)
        self.model_code=QLineEdit(); self.model_name=QLineEdit(); self.model_chemistry=QLineEdit("NiMH")
        self.model_voltage=self._num(0,100,3); self.model_capacity=self._num(0,1000000,1)
        self.model_manufacturer=QLineEdit(); self.model_notes=QLineEdit()
        for label,w in (("Model Code",self.model_code),("Model Name",self.model_name),("Chemistry",self.model_chemistry),
                        ("Nominal Voltage (V)",self.model_voltage),("Nominal Capacity (mAh)",self.model_capacity),
                        ("Manufacturer",self.model_manufacturer),("Notes",self.model_notes)): form.addRow(label,w)
        b=QPushButton("REGISTER BATTERY MODEL"); b.clicked.connect(self._register_model); form.addRow(b)
        self.model_list=QListWidget(); form.addRow("Registered Models",self.model_list); tabs.addTab(page,"1. BATTERY MODEL")

        page=QWidget(); layout=QVBoxLayout(page); form=QFormLayout()
        self.model=QComboBox(); self.iid=QLineEdit(); self.serial=QLineEdit(); self.nickname=QLineEdit(); self.notes=QLineEdit()
        self.status_combo=QComboBox(); self.status_combo.addItems(["NEW","ACTIVE","RETIRED","ARCHIVED"])
        for label,w in (("Battery Model",self.model),("Instance ID",self.iid),("Serial Number",self.serial),("Nickname",self.nickname),
                        ("Lifecycle Status",self.status_combo),("Notes",self.notes)): form.addRow(label,w)
        layout.addLayout(form)
        buttons=QHBoxLayout(); new_btn=QPushButton("NEW INSTANCE"); edit_btn=QPushButton("EDIT SELECTED"); save_btn=QPushButton("REGISTER / UPDATE BATTERY INSTANCE")
        new_btn.clicked.connect(self._new_instance); edit_btn.clicked.connect(self._edit_selected_instance); save_btn.clicked.connect(self._register_instance)
        buttons.addWidget(new_btn); buttons.addWidget(edit_btn); buttons.addWidget(save_btn); layout.addLayout(buttons)
        self.instance_list=QListWidget(); self.instance_list.itemDoubleClicked.connect(lambda item:self._load_instance_into_form(item.data(32)))
        layout.addWidget(QLabel("Registered Battery Instances")); layout.addWidget(self.instance_list); tabs.addTab(page,"2. BATTERY INSTANCE")

        page=QWidget(); layout=QVBoxLayout(page); form=QFormLayout()
        self.session=QComboBox(); self.session.currentIndexChanged.connect(self._load_selected_session_result)
        self.result_instance=QComboBox(); self.version=QLineEdit("battery-benchmark-v1")
        self.count=QSpinBox(); self.count.setRange(0,100000000)
        self.avg_v=self._num(0,10,4); self.avg_i=self._num(0,100,4); self.avg_p=self._num(0,1000,4)
        self.max_i=self._num(0,100,4); self.max_p=self._num(0,1000,4); self.duration=self._num(0,1000000,2)
        self.drop=self._num(-10,10,4); self.cap=self._num(0,100000,3); self.energy=self._num(0,100000,3)
        fields=(("Session / Measurement",self.session),("Battery Instance",self.result_instance),("Analysis Version",self.version),
                ("Measurement Count",self.count),("Average Voltage (V)",self.avg_v),("Average Current (A)",self.avg_i),
                ("Average Power (W)",self.avg_p),("Max Current (A)",self.max_i),("Max Power (W)",self.max_p),
                ("Discharge Time (s)",self.duration),("Voltage Drop (V)",self.drop),("Capacity (mAh)",self.cap),("Energy (Wh)",self.energy))
        for label,w in fields: form.addRow(label,w)
        layout.addLayout(form)
        self.session_info=QLabel("Session information: not selected"); layout.addWidget(self.session_info)
        confirm=QGroupBox("CONFIRMATION"); cl=QVBoxLayout(confirm)
        self.quality=QPushButton("Measurement quality: NOT CONFIRMED"); self.quality.setCheckable(True)
        self.quality.clicked.connect(lambda c:self.quality.setText("Measurement quality: OK" if c else "Measurement quality: NOT CONFIRMED"))
        self.operator=QPushButton("Operator confirmation: NOT CONFIRMED"); self.operator.setCheckable(True)
        self.operator.clicked.connect(lambda c:self.operator.setText("Operator confirmation: CONFIRMED" if c else "Operator confirmation: NOT CONFIRMED"))
        cl.addWidget(self.quality); cl.addWidget(self.operator); layout.addWidget(confirm)
        b=QPushButton("REGISTER CONFIRMED BENCHMARK RESULT"); b.clicked.connect(self._register_result); layout.addWidget(b)
        self.status=QLabel("Not registered"); layout.addWidget(self.status); tabs.addTab(page,"3. BENCHMARK RESULT")

    @staticmethod
    def _num(a,b,dec):
        w=QDoubleSpinBox(); w.setRange(a,b); w.setDecimals(dec); return w

    def _new_instance(self):
        self.iid.clear(); self.iid.setReadOnly(False); self.serial.clear(); self.nickname.clear(); self.notes.clear(); self.status_combo.setCurrentText("NEW")
        if self.model.count(): self.model.setCurrentIndex(0)

    def _edit_selected_instance(self):
        item=self.instance_list.currentItem()
        if item is None:
            QMessageBox.warning(self,"Battery Instance","編集するInstanceを一覧から選択してください。"); return
        self._load_instance_into_form(item.data(32))

    def _load_models(self):
        self.model.clear(); self.model_list.clear()
        with self._db() as db:
            rows=db.execute("SELECT battery_model_id,model_code,name FROM battery_model WHERE COALESCE(is_deleted,0)=0 ORDER BY model_code").fetchall()
        for mid,code,name in rows:
            self.model.addItem(f"{code} / {name}",mid); self.model_list.addItem(f"{code} / {name} (ID {mid})")

    def _register_model(self):
        code=self.model_code.text().strip(); name=self.model_name.text().strip()
        if not code or not name:
            QMessageBox.warning(self,"Battery Model","Model CodeとModel Nameを指定してください。"); return
        try:
            with self._db() as db:
                db.execute("INSERT INTO battery_model(model_code,name,chemistry,nominal_voltage,capacity_nominal_mah,manufacturer,notes) VALUES(?,?,?,?,?,?,?)",
                           (code,name,self.model_chemistry.text().strip() or None,self.model_voltage.value() or None,self.model_capacity.value() or None,self.model_manufacturer.text().strip() or None,self.model_notes.text().strip() or None)); db.commit()
            self._load_models(); QMessageBox.information(self,"Battery Model",f"{code} を登録しました。")
        except sqlite3.Error as exc: QMessageBox.critical(self,"Battery Model",f"登録できません。\n{exc}")

    def _load_instances(self):
        self.result_instance.clear(); self.instance_list.clear(); self.model.clear()
        with self._db() as db:
            models=db.execute("SELECT battery_model_id,model_code,name FROM battery_model WHERE COALESCE(is_deleted,0)=0 ORDER BY model_code").fetchall()
            rows=db.execute("SELECT bi.instance_id,bi.serial_number,bi.nickname,bm.model_code,COALESCE(bi.lifecycle_status,'ACTIVE') FROM battery_instance bi LEFT JOIN battery_model bm ON bm.battery_model_id=bi.battery_model_id WHERE COALESCE(bi.is_deleted,0)=0 ORDER BY bi.instance_id").fetchall()
        for mid,code,name in models: self.model.addItem(f"{code} / {name}",mid)
        for iid,serial,nickname,code,status in rows:
            text=f"{iid} | {code or '-'} | {nickname or '-'} | SN:{serial or '-'} | {status}"
            self.result_instance.addItem(text,iid); item=self.instance_list.addItem(text); self.instance_list.item(self.instance_list.count()-1).setData(32,iid)

    def _load_instance_into_form(self, iid):
        if not iid: return
        with self._db() as db:
            row=db.execute("SELECT battery_model_id,serial_number,nickname,notes,COALESCE(lifecycle_status,'ACTIVE') FROM battery_instance WHERE instance_id=?",(iid,)).fetchone()
        if not row: return
        mid,serial,nickname,notes,status=row; self.iid.setText(str(iid)); self.iid.setReadOnly(True); idx=self.model.findData(mid); self.model.setCurrentIndex(idx)
        self.serial.setText(serial or ''); self.nickname.setText(nickname or ''); self.notes.setText(notes or ''); self.status_combo.setCurrentText(status)

    def _register_instance(self):
        iid=self.iid.text().strip()
        if not iid or self.model.currentData() is None:
            QMessageBox.warning(self,"Battery Instance","Instance IDとBattery Modelを指定してください。"); return
        try:
            with self._db() as db:
                exists=db.execute("SELECT 1 FROM battery_instance WHERE instance_id=?",(iid,)).fetchone()
                if exists:
                    db.execute("UPDATE battery_instance SET battery_model_id=?,serial_number=?,nickname=?,notes=?,lifecycle_status=?,is_deleted=?,updated_at=CURRENT_TIMESTAMP WHERE instance_id=?",
                               (self.model.currentData(),self.serial.text().strip() or None,self.nickname.text().strip() or None,self.notes.text().strip() or None,self.status_combo.currentText(),0 if self.status_combo.currentText()!='ARCHIVED' else 1,iid))
                else:
                    db.execute("INSERT INTO battery_instance(instance_id,battery_model_id,serial_number,nickname,notes,lifecycle_status) VALUES(?,?,?,?,?,?)",
                               (iid,self.model.currentData(),self.serial.text().strip() or None,self.nickname.text().strip() or None,self.notes.text().strip() or None,self.status_combo.currentText()))
                db.commit()
            self._load_instances(); QMessageBox.information(self,"Battery Instance",f"{iid} を保存しました。")
        except sqlite3.Error as exc: QMessageBox.critical(self,"Battery Instance",f"保存できません。\n{exc}")

    def _load_sessions(self):
        self.session.blockSignals(True); self.session.clear()
        with self._db() as db:
            cols={r[1] for r in db.execute("PRAGMA table_info(measurement_session)").fetchall()}
            if 'result' in cols and 'end_datetime' in cols:
                rows=db.execute("SELECT session_id,instance_id,start_datetime,end_datetime,result FROM measurement_session WHERE result='COMPLETE' ORDER BY COALESCE(end_datetime,start_datetime,created_at) DESC").fetchall()
            elif 'end_datetime' in cols:
                rows=db.execute("SELECT session_id,instance_id,start_datetime,end_datetime,'COMPLETE' FROM measurement_session WHERE end_datetime IS NOT NULL ORDER BY COALESCE(end_datetime,start_datetime,created_at) DESC").fetchall()
            else:
                rows=db.execute("SELECT session_id,instance_id,start_time,end_time,status FROM measurement_session WHERE status='COMPLETE' ORDER BY COALESCE(end_time,start_time) DESC").fetchall()
            measurement_rows={}
            for sid,*_ in rows:
                m=db.execute("SELECT DISTINCT instance_id,record_type FROM measurement WHERE session_id=? AND instance_id IS NOT NULL ORDER BY id",(sid,)).fetchall()
                measurement_rows[sid]=m
        for sid,mi,start,end,result in rows:
            m=measurement_rows.get(sid,[]); instances=','.join(sorted({str(x[0]) for x in m}))
            records='/'.join(sorted({str(x[1]) for x in m if x[1]}))
            label=f"Session {sid} | Instance {instances or mi or '-'} | {records or 'MEASUREMENT'} | {start or '-'} -> {end or '-'} | {result or 'COMPLETE'}"
            self.session.addItem(label,sid)
        self.session.blockSignals(False)
        if self.session.count(): self.session.setCurrentIndex(0); self._load_selected_session_result()
        else: self.session_info.setText("Session information: no completed sessions")

    def _load_selected_session_result(self):
        sid=self.session.currentData()
        if not sid: return
        try:
            with self._db() as db:
                scols={r[1] for r in db.execute("PRAGMA table_info(measurement_session)").fetchall()}
                if 'start_datetime' in scols:
                    srow=db.execute("SELECT instance_id,start_datetime,end_datetime,result FROM measurement_session WHERE session_id=?",(sid,)).fetchone()
                else:
                    srow=db.execute("SELECT instance_id,start_time,end_time,status FROM measurement_session WHERE session_id=?",(sid,)).fetchone()
                mrows=db.execute("SELECT elapsed_time,voltage1,voltage2,current1,current2,power,peak_current,peak_power,state FROM measurement WHERE session_id=? ORDER BY elapsed_time,id",(sid,)).fetchall()
            if not srow or not mrows: return
            session_iid,start,end,result=srow
            instance_ids={r[0] for r in mrows if r[0]}
            iid=next(iter(instance_ids),session_iid)
            idx=self.result_instance.findData(iid)
            if idx>=0: self.result_instance.setCurrentIndex(idx)
            volt=[]; curr=[]; power=[]; times=[]; peaks_i=[]; peaks_p=[]
            for elapsed,v1,v2,i1,i2,p,pi,pp,state in mrows:
                vs=[v for v in (v1,v2) if v is not None]; cs=[v for v in (i1,i2) if v is not None]
                if vs: volt.append(sum(vs)/len(vs))
                if cs: curr.append(sum(cs)/len(cs))
                if p is not None: power.append(p)
                if elapsed is not None: times.append(float(elapsed))
                if pi is not None: peaks_i.append(float(pi))
                if pp is not None: peaks_p.append(float(pp))
            self.count.setValue(len(mrows))
            self.avg_v.setValue(sum(volt)/len(volt) if volt else 0)
            self.avg_i.setValue(sum(curr)/len(curr) if curr else 0)
            self.avg_p.setValue(sum(power)/len(power) if power else 0)
            self.max_i.setValue(max(peaks_i or curr or [0]))
            self.max_p.setValue(max(peaks_p or power or [0]))
            duration=max(times) if times else 0; self.duration.setValue(duration)
            self.drop.setValue((max(volt)-min(volt)) if volt else 0)
            capacity=0.0; energy=0.0
            for n in range(1,len(mrows)):
                t0=mrows[n-1][0]; t1=mrows[n][0]
                if t0 is None or t1 is None: continue
                dt=max(0.0,float(t1)-float(t0)); c0=[x for x in mrows[n-1][3:5] if x is not None]; c1=[x for x in mrows[n][3:5] if x is not None]
                p0=mrows[n-1][5] or 0; p1=mrows[n][5] or 0
                if c0 and c1: capacity += ((sum(c0)/len(c0))+(sum(c1)/len(c1)))/2*dt/3600*1000
                energy += ((p0+p1)/2)*dt/3600
            self.cap.setValue(capacity); self.energy.setValue(energy)
            self.session_info.setText(f"Session {sid} | Instance {iid or '-'} | Result {result or 'COMPLETE'} | Start {start or '-'} | End {end or '-'} | {len(mrows)} samples")
            self.status.setText(f"Loaded measurement result: Session {sid}")
        except sqlite3.Error as exc:
            self.session_info.setText(f"Session read error: {exc}")

    def _register_result(self):
        sid=self.session.currentData() or self.session.currentText().strip(); iid=self.result_instance.currentData()
        if not sid or not iid:
            QMessageBox.warning(self,"Benchmark Result","SessionとBattery Instanceを指定してください。"); return
        try:
            with self._db() as db:
                cols={r[1] for r in db.execute("PRAGMA table_info(measurement_session)").fetchall()}
                if 'result' in cols:
                    row=db.execute("SELECT result FROM measurement_session WHERE session_id=?",(sid,)).fetchone(); session_result=row[0] if row else None
                else:
                    row=db.execute("SELECT end_time FROM measurement_session WHERE session_id=?",(sid,)).fetchone(); session_result='COMPLETE' if row and row[0] else 'RUNNING'
            if not row: raise ManualRegistrationError("SessionがDBに存在しません")
            validate_manual_registration(session_result=session_result,quality_ok=self.quality.isChecked(),operator_confirmed=self.operator.isChecked())
            values=(sid,iid,self.version.text().strip() or "battery-benchmark-v1",self.count.value(),self.avg_v.value(),self.avg_i.value(),self.avg_p.value(),self.max_i.value(),self.max_p.value(),self.duration.value(),self.drop.value(),self.cap.value(),self.energy.value())
            with self._db() as db:
                db.execute("INSERT OR REPLACE INTO battery_benchmark_result (session_id,instance_id,analysis_version,measurement_count,avg_voltage,avg_current,avg_power,max_current,max_power,discharge_time_s,voltage_drop,capacity_mah,energy_wh) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",values); db.commit()
            self.status.setText(f"REGISTERED: Session {sid} / Instance {iid}"); QMessageBox.information(self,"Benchmark Result","正式Benchmark Resultとして登録しました。")
        except (ManualRegistrationError,sqlite3.Error) as exc: QMessageBox.critical(self,"Benchmark Result",str(exc))

    def refresh_all(self):
        self._load_models(); self._load_instances(); self._load_sessions()
