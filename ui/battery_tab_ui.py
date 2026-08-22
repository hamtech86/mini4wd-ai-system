"""Integrated Battery operation tab.

Top-level window owns the BatterySerial connection. This tab provides
5A operation, status/live data, Instance assignment, and manual post-test
registration. Measurements are retained in-memory until the operator confirms
registration, then persisted as the source records plus derived Benchmark Result.
"""
import sqlite3
import uuid
from datetime import datetime
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel, QPushButton, QComboBox, QTabWidget, QMessageBox
from battery_system.serial import BatterySerial
from ui.battery_database_ui import BatteryDatabaseDialog

class BatteryTab(QWidget):
    def __init__(self, db_path, transport=None, parent=None):
        super().__init__(parent); self.db_path=str(db_path); self.transport=transport or BatterySerial()
        self.samples={1:[],2:[]}; self.latest_status={1:"IDLE",2:"IDLE"}; self.session_ids={1:None,2:None}; self.session_started={1:None,2:None}
        self._build(); self._load_models_and_instances(); self.timer=QTimer(self); self.timer.setInterval(100); self.timer.timeout.connect(self.poll_serial); self._set_controls_enabled(False)

    def _db(self): return sqlite3.connect(self.db_path)
    def _build(self):
        root=QVBoxLayout(self); tabs=QTabWidget(); operation=QWidget(); op=QVBoxLayout(operation)
        status=QGroupBox("STATUS"); sg=QGridLayout(status); self.status_labels={}
        for col,ch in enumerate(("ALL","CH1","CH2")): self.status_labels[ch]=QLabel(f"{ch}: IDLE"); sg.addWidget(self.status_labels[ch],0,col)
        op.addWidget(status)
        assignment=QGroupBox("BATTERY INSTANCE ASSIGNMENT"); ar=QVBoxLayout(assignment); mr=QHBoxLayout(); self.model=QComboBox(); mr.addWidget(QLabel("Battery Model")); mr.addWidget(self.model); ar.addLayout(mr); ir=QHBoxLayout(); self.ch1_instance=QComboBox(); self.ch2_instance=QComboBox(); ir.addWidget(QLabel("CH1 Instance")); ir.addWidget(self.ch1_instance); ir.addWidget(QLabel("CH2 Instance")); ir.addWidget(self.ch2_instance); ar.addLayout(ir); self.assignment_status=QLabel("Battery Model / Instanceを読み込み中..."); ar.addWidget(self.assignment_status); op.addWidget(assignment)
        controls=QGroupBox("5A DISCHARGE"); cr=QGridLayout(controls)
        for col,name in enumerate(("ALL","CH1","CH2")): cr.addWidget(QLabel(name),0,col)
        self.all_start=QPushButton("START"); self.ch1_start=QPushButton("START"); self.ch2_start=QPushButton("START"); self.all_stop=QPushButton("STOP"); self.ch1_stop=QPushButton("STOP"); self.ch2_stop=QPushButton("STOP")
        for col,b in enumerate((self.all_start,self.ch1_start,self.ch2_start)): cr.addWidget(b,1,col)
        for col,b in enumerate((self.all_stop,self.ch1_stop,self.ch2_stop)): cr.addWidget(b,2,col)
        self.all_start.clicked.connect(lambda:self.start_channel(None)); self.ch1_start.clicked.connect(lambda:self.start_channel(1)); self.ch2_start.clicked.connect(lambda:self.start_channel(2)); self.all_stop.clicked.connect(lambda:self.stop_channel(None)); self.ch1_stop.clicked.connect(lambda:self.stop_channel(1)); self.ch2_stop.clicked.connect(lambda:self.stop_channel(2)); op.addWidget(controls)
        live=QGroupBox("LIVE DATA"); grid=QGridLayout(live); self.live_labels={}; fields=(("CH1","Voltage"),("CH1","Current"),("CH1","PWM"),("CH1","Time"),("CH2","Voltage"),("CH2","Current"),("CH2","PWM"),("CH2","Time"))
        for i,(ch,f) in enumerate(fields): self.live_labels[(ch,f)]=QLabel(f"{ch} {f}: --"); grid.addWidget(self.live_labels[(ch,f)],i//4,i%4)
        op.addWidget(live)
        result=QGroupBox("RESULT / MANUAL REGISTRATION"); rr=QGridLayout(result); self.result_labels={}
        for row,ch in enumerate(("CH1","CH2")): self.result_labels[ch]=QLabel(f"{ch} Result: no completed measurement"); rr.addWidget(self.result_labels[ch],row,0,1,2)
        self.register_result_button=QPushButton("REGISTER RESULT TO DATABASE"); self.register_result_button.setEnabled(False); self.register_result_button.clicked.connect(self.register_results); rr.addWidget(self.register_result_button,2,0,1,2); op.addWidget(result)
        op.addWidget(QLabel("実測値は終了後に確認し、登録ボタンを押した時点でMeasurementとBenchmark ResultをDBへ保存します。")); tabs.addTab(operation,"5A DISCHARGE")
        db_page=QWidget(); db_layout=QVBoxLayout(db_page); db_button=QPushButton("OPEN BATTERY INSTANCE / RESULT DATABASE"); db_button.clicked.connect(self.open_database); db_layout.addWidget(db_button); db_layout.addStretch(1); tabs.addTab(db_page,"DATABASE"); root.addWidget(tabs)

    def _load_models_and_instances(self):
        self.model.clear(); self.ch1_instance.clear(); self.ch2_instance.clear()
        try:
            with self._db() as db:
                models=db.execute("SELECT battery_model_id,model_code,name FROM battery_model WHERE COALESCE(is_deleted,0)=0 ORDER BY model_code").fetchall(); instances=db.execute("SELECT bi.instance_id,bi.battery_model_id,bi.nickname,bm.model_code FROM battery_instance bi LEFT JOIN battery_model bm ON bm.battery_model_id=bi.battery_model_id WHERE COALESCE(bi.is_deleted,0)=0 ORDER BY bi.instance_id").fetchall()
            for mid,code,name in models: self.model.addItem(f"{code} / {name}",mid)
            for iid,mid,nickname,code in instances:
                text=f"{iid} / {nickname or code or ''}".rstrip(" /"); self.ch1_instance.addItem(text,iid); self.ch2_instance.addItem(text,iid)
            self.assignment_status.setText("Battery Modelを選択し、CH1 / CH2 Instanceを指定してください" if models and instances else "Battery Model / InstanceをDATABASEから登録してください")
        except sqlite3.Error as exc: self.assignment_status.setText("Battery Model / Instanceを読み込めません"); QMessageBox.warning(self,"Battery",f"Battery Model / Instanceを読み込めません。\n{exc}")

    def _validate_instance_assignment(self, warn=False):
        a=self.ch1_instance.currentData(); b=self.ch2_instance.currentData()
        if a is not None and b is not None and a==b:
            self.assignment_status.setText("CH1 / CH2: 同じInstance（START時に警告）")
            if warn:
                QMessageBox.warning(self,"Battery Instance","CH1とCH2に同じBattery Instanceが指定されています。\n同じInstanceを同時にSTARTすることはできません。")
            return False
        self.assignment_status.setText("CH1 / CH2: Assignment OK" if a is not None and b is not None else "Battery Modelを選択し、CH1 / CH2 Instanceを指定してください"); return True

    def _set_controls_enabled(self,enabled):
        have1=self.ch1_instance.currentData() is not None; have2=self.ch2_instance.currentData() is not None
        for b in (self.ch1_start,self.ch1_stop,self.ch2_start,self.ch2_stop): b.setEnabled(enabled and have1 and have2)
        self.all_start.setEnabled(enabled and have1 and have2); self.all_stop.setEnabled(enabled)

    def set_connected(self,connected): self._set_controls_enabled(connected); self.timer.start() if connected else self.timer.stop()

    def _status(self,ch,value):
        self.latest_status[ch]=value; self.status_labels[f"CH{ch}"].setText(f"CH{ch}: {value}"); self.status_labels["ALL"].setText(f"ALL: {self.latest_status[1]} / {self.latest_status[2]}")

    def _same_instance_conflict(self, channel):
        a=self.ch1_instance.currentData(); b=self.ch2_instance.currentData()
        if a is None or b is None: return False
        if a != b: return False
        if channel is None: return True
        other=2 if channel==1 else 1
        return self.latest_status[other] not in ("IDLE","STOPPED","DISCONNECTED")

    def start_channel(self,channel):
        if not self.transport.connected: return
        a=self.ch1_instance.currentData(); b=self.ch2_instance.currentData()
        if a is None or b is None:
            QMessageBox.warning(self,"Battery Instance","CH1 / CH2のBattery Instanceを指定してください。"); return
        if self._same_instance_conflict(channel):
            QMessageBox.warning(self,"Battery Instance Conflict",f"CH1: {a}\nCH2: {b}\n\n同じBattery Instanceを同時に使用することはできません。\nInstanceを変更してください。"); return
        if channel is None: self.session_started={1:datetime.now().isoformat(timespec="seconds"),2:datetime.now().isoformat(timespec="seconds")}; self.samples={1:[],2:[]}
        else: self.session_started[channel]=datetime.now().isoformat(timespec="seconds"); self.samples[channel]=[]
        if not self.transport.start(channel): QMessageBox.warning(self,"Battery","STARTコマンドを送信できませんでした。"); return
        if channel is None: self._status(1,"STARTING"); self._status(2,"STARTING")
        else: self._status(channel,"STARTING")
        self.register_result_button.setEnabled(False)

    def stop_channel(self,channel):
        if not self.transport.connected: return
        if not self.transport.stop(channel): QMessageBox.warning(self,"Battery","STOPコマンドを送信できませんでした。"); return
        if channel is None: self._status(1,"STOPPING"); self._status(2,"STOPPING")
        else: self._status(channel,"STOPPING")

    def poll_serial(self):
        for line in self.transport.read_lines():
            text=line.strip()
            if text.startswith("STATUS"):
                parts=text.split(',')
                if len(parts)>=3: self._status(1,parts[1].strip()); self._status(2,parts[2].strip())
                continue
            sample=self.transport.parse_data(text)
            if sample is None: continue
            prefix=f"CH{sample.channel}"; self.samples[sample.channel].append(sample); self.live_labels[(prefix,"Voltage")].setText(f"{prefix} Voltage: {sample.voltage:.3f} V"); self.live_labels[(prefix,"Current")].setText(f"{prefix} Current: {sample.current:.3f} A"); self.live_labels[(prefix,"PWM")].setText(f"{prefix} PWM: {sample.pwm}"); self.live_labels[(prefix,"Time")].setText(f"{prefix} Time: {sample.elapsed_sec:.1f} s"); self.result_labels[prefix].setText(f"{prefix} Result: {len(self.samples[sample.channel])} samples / latest {sample.voltage:.3f} V, {sample.current:.3f} A")
            if self.latest_status[1] in ("STOPPED","IDLE") or self.latest_status[2] in ("STOPPED","IDLE"): self.register_result_button.setEnabled(bool(self.samples[1] or self.samples[2]))

    @staticmethod
    def _stats(samples):
        samples=sorted(samples,key=lambda x:x.elapsed_sec); n=len(samples); avg_v=sum(x.voltage for x in samples)/n; avg_i=sum(x.current for x in samples)/n; powers=[x.voltage*x.current for x in samples]; avg_p=sum(powers)/n; max_i=max(x.current for x in samples); max_p=max(powers); duration=max(x.elapsed_sec for x in samples)-min(x.elapsed_sec for x in samples); cap=0.0; energy=0.0
        for a,b in zip(samples,samples[1:]):
            dt=max(0.0,b.elapsed_sec-a.elapsed_sec)/3600.0; cap+=(a.current+b.current)*0.5*dt*1000.0; energy+=(a.voltage*a.current+b.voltage*b.current)*0.5*dt
        return n,avg_v,avg_i,avg_p,max_i,max_p,duration,cap,energy

    def register_results(self):
        completed=[]
        for ch in (1,2):
            samples=self.samples[ch]; iid=self.ch1_instance.currentData() if ch==1 else self.ch2_instance.currentData()
            if samples and iid: completed.append((ch,iid,self._stats(samples)))
        if not completed: QMessageBox.warning(self,"Battery Result","登録できる測定がありません。"); return
        if QMessageBox.question(self,"Battery Result","放電結果を確認しました。MeasurementとBenchmark Resultをデータベースへ登録しますか？",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes: return
        try:
            with self._db() as db:
                for ch,iid,stats in completed:
                    n,av,ai,ap,mi,mp,dur,cap,energy=stats; sid=str(uuid.uuid4()); start=self.session_started[ch] or datetime.now().isoformat(timespec="seconds"); end=datetime.now().isoformat(timespec="seconds")
                    db.execute("INSERT INTO measurement_session(session_id,measurement_type,status,start_time,end_time,measurement_count,operator,notes,schema_version,firmware_version) VALUES(?,?,?,?,?,?,?,?,?,?)",(sid,"BATTERY_5A","COMPLETE",start,end,n,"USER",f"Integrated Battery UI CH{ch}; manual result registration","battery-db-v1","UNKNOWN"))
                    for s in self.samples[ch]: db.execute("INSERT INTO measurement(session_id,record_type,device_model,instance_id,elapsed_time,voltage1,current1,pwm,state,power,peak_current,peak_voltage,peak_pwm) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",(sid,"BATTERY_5A","BATTERY_5A",iid,s.elapsed_sec,s.voltage,s.current,s.pwm,"MEASURED",s.voltage*s.current,s.current,s.voltage,s.pwm))
                    db.execute("INSERT INTO battery_benchmark_result(session_id,instance_id,analysis_version,measurement_count,avg_voltage,avg_current,avg_power,max_current,max_power,discharge_time_s,capacity_mah,energy_wh) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(sid,iid,"battery-benchmark-v1",n,av,ai,ap,mi,mp,dur,cap,energy))
                db.commit()
            QMessageBox.information(self,"Battery Result","MeasurementとBenchmark Resultを登録しました。"); self.register_result_button.setEnabled(False)
        except sqlite3.Error as exc: QMessageBox.critical(self,"Battery Result",f"登録できません。\n{exc}")

    def open_database(self):
        dialog=BatteryDatabaseDialog(self.db_path,self); dialog.exec_(); self._load_models_and_instances()
