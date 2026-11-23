"""Operator UI for Battery Model, Instance and confirmed Benchmark registration."""
from __future__ import annotations
import sqlite3
from pathlib import Path
from PyQt5.QtWidgets import (QComboBox, QDialog, QFormLayout, QGroupBox, QLabel,
    QLineEdit, QMessageBox, QPushButton, QDoubleSpinBox, QSpinBox, QTabWidget,
    QVBoxLayout, QWidget, QListWidget, QHBoxLayout)
from battery_system.manual_result_registration import validate_manual_registration, ManualRegistrationError
from database.path_resolver import connect_database, resolve_database_path


def is_legacy_channel_ambiguous(session_notes):
    """Identify records written by the legacy UI that did not persist CH identity.

    Notes are used only to quarantine known legacy rows, never to infer CH1/CH2.
    """
    return bool(session_notes and str(session_notes).startswith("Integrated Battery UI CH"))


def infer_battery_session_channel(scope_keys):
    """Resolve CH only from an explicit persisted Scope Key, never column names."""
    values = {str(value).strip() for value in scope_keys if value is not None and str(value).strip()}
    if len(values) != 1:
        return None
    return {"BATTERY:CH1": "CH1", "BATTERY:CH2": "CH2"}.get(next(iter(values)))


class BatteryDatabaseDialog(QDialog):
    def __init__(self, db_path: str | Path, parent=None):
        super().__init__(parent)
        self.db_path = str(resolve_database_path(db_path, required_tables=("battery_model", "battery_instance", "battery_benchmark_result")))
        self.setWindowTitle("BATTERY DATABASE / MODEL / INSTANCE / MANUAL REGISTRATION")
        self.resize(900, 700)
        self._build()
        self.refresh_all()
        self.raise_(); self.activateWindow()

    def _db(self):
        return connect_database(self.db_path)

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
        self.session=QComboBox(); self._channel_identity=None; self.session.currentIndexChanged.connect(self._load_selected_session_result)
        self.result_instance=QComboBox(); self.version=QLineEdit("battery-benchmark-v2")
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
        self._channel_identity=None
        sid=self.session.currentData()
        if not sid: return
        try:
            with self._db() as db:
                scols={r[1] for r in db.execute("PRAGMA table_info(measurement_session)").fetchall()}
                if 'start_datetime' in scols:
                    note_expr = "notes" if "notes" in scols else "NULL"
                    srow=db.execute(f"SELECT instance_id,start_datetime,end_datetime,result,{note_expr} FROM measurement_session WHERE session_id=?",(sid,)).fetchone()
                else:
                    note_expr = "notes" if "notes" in scols else "NULL"
                    srow=db.execute(f"SELECT instance_id,start_time,end_time,status,{note_expr} FROM measurement_session WHERE session_id=?",(sid,)).fetchone()
                mcols={r[1] for r in db.execute("PRAGMA table_info(measurement)").fetchall()}
                session_scope = db.execute(
                    "SELECT scope_key FROM measurement_session WHERE session_id=?", (sid,)
                ).fetchone()[0] if "scope_key" in scols else None
                measurement_scopes = [
                    row[0] for row in db.execute(
                        "SELECT DISTINCT scope_key FROM measurement WHERE session_id=? AND scope_key IS NOT NULL",
                        (sid,),
                    ).fetchall()
                ] if "scope_key" in mcols else []
                mrows=db.execute(
                    "SELECT elapsed_time,voltage1,voltage2,current1,current2,state FROM measurement WHERE session_id=? ORDER BY elapsed_time,id",
                    (sid,),
                ).fetchall()
            if not srow or not mrows: return
            session_iid,start,end,result,session_notes=srow
            if is_legacy_channel_ambiguous(session_notes):
                for widget in (self.count,self.avg_v,self.avg_i,self.avg_p,self.max_i,self.max_p,self.duration,self.drop,self.cap,self.energy):
                    widget.setValue(0)
                self.session_info.setText(
                    f"Session {sid} | Channel UNKNOWN | 旧UIがCH識別を保存していないため解析・登録できません"
                )
                self.status.setText("NOT REGISTERABLE: legacy channel identity missing")
                return
            channel=infer_battery_session_channel([session_scope, *measurement_scopes])
            if channel is None:
                for widget in (self.count,self.avg_v,self.avg_i,self.avg_p,self.max_i,self.max_p,self.duration,self.drop,self.cap,self.energy):
                    widget.setValue(0)
                self.session_info.setText(
                    f"Session {sid} | Channel UNKNOWN | 明示Scope Keyが保存されていないため解析・登録できません"
                )
                self.status.setText("NOT REGISTERABLE: channel identity unknown")
                return
            self._channel_identity=channel
            voltage_index=1 if channel=="CH1" else 2
            current_index=3 if channel=="CH1" else 4
            with self._db() as db:
                instance_rows=db.execute(
                    "SELECT DISTINCT instance_id FROM measurement WHERE session_id=? AND instance_id IS NOT NULL",
                    (sid,),
                ).fetchall()
            iid=next((row[0] for row in instance_rows),session_iid)
            idx=self.result_instance.findData(iid)
            if idx>=0: self.result_instance.setCurrentIndex(idx)

            paired=[]; times=[]
            for row in mrows:
                elapsed=row[0]
                voltage=row[voltage_index]
                current=row[current_index]
                if voltage is None or current is None:
                    continue
                try:
                    voltage=float(voltage); current=float(current)
                    if not (math.isfinite(voltage) and math.isfinite(current)):
                        continue
                    if voltage == 0.0 or current == 0.0:
                        self._channel_identity=None
                        self.session_info.setText(
                            f"Session {sid} | Channel {channel} | 選択CHの0.0値を検出: Validity UNKNOWN"
                        )
                        self.status.setText("NOT REGISTERABLE: selected-channel zero validity UNKNOWN")
                        return
                    elapsed=float(elapsed)
                    if not math.isfinite(elapsed):
                        continue
                except (TypeError,ValueError):
                    continue
                paired.append((elapsed,voltage,current))
            if not paired:
                self._channel_identity=None
                self.session_info.setText(f"Session {sid} | Channel {channel} | 有効なV/Iペアなし")
                self.status.setText("NOT REGISTERABLE: no valid channel samples")
                return
            paired.sort(key=lambda item:item[0])
            times=[item[0] for item in paired]
            volt=[item[1] for item in paired]
            curr=[item[2] for item in paired]
            power=[v*i for v,i in zip(volt,curr)]
            self.count.setValue(len(mrows))
            self.avg_v.setValue(sum(volt)/len(volt))
            self.avg_i.setValue(sum(curr)/len(curr))
            self.avg_p.setValue(sum(power)/len(power))
            self.max_i.setValue(max(curr))
            self.max_p.setValue(max(power))
            self.duration.setValue(max(times)-min(times) if len(times)>1 else 0)
            self.drop.setValue(volt[0]-volt[-1] if len(volt)>1 else 0)
            capacity=0.0; energy=0.0
            for a,b in zip(paired,paired[1:]):
                dt=max(0.0,b[0]-a[0])/3600.0
                capacity += (a[2]+b[2])*0.5*dt*1000.0
                energy += (a[1]*a[2]+b[1]*b[2])*0.5*dt
            self.cap.setValue(capacity); self.energy.setValue(energy)
            self.session_info.setText(
                f"Session {sid} | {channel} | Instance {iid or '-'} | Result {result or 'COMPLETE'} | Start {start or '-'} | End {end or '-'} | {len(paired)} valid samples"
            )
            self.status.setText(f"Loaded {channel} result: Session {sid}")
        except sqlite3.Error as exc:
            self._channel_identity=None
            self.session_info.setText(f"Session read error: {exc}")

    def _register_result(self):
        sid=self.session.currentData() or self.session.currentText().strip(); iid=self.result_instance.currentData()
        if self._channel_identity not in ("CH1", "CH2"):
            QMessageBox.warning(self,"Benchmark Result","Channel identityまたはSample ValidityがUNKNOWNのため登録できません。")
            return
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
            values=(sid,iid,self.version.text().strip() or "battery-benchmark-v2",self.count.value(),self.avg_v.value(),self.avg_i.value(),self.avg_p.value(),self.max_i.value(),self.max_p.value(),self.duration.value(),self.drop.value(),self.cap.value(),self.energy.value())
            with self._db() as db:
                db.execute("INSERT OR REPLACE INTO battery_benchmark_result (session_id,instance_id,analysis_version,measurement_count,avg_voltage,avg_current,avg_power,max_current,max_power,discharge_time_s,voltage_drop,capacity_mah,energy_wh) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",values); db.commit()
            self.status.setText(f"REGISTERED: Session {sid} / Instance {iid}"); QMessageBox.information(self,"Benchmark Result","正式Benchmark Resultとして登録しました。")
        except (ManualRegistrationError,sqlite3.Error) as exc: QMessageBox.critical(self,"Benchmark Result",str(exc))

    def refresh_all(self):
        self._load_models(); self._load_instances(); self._load_sessions()