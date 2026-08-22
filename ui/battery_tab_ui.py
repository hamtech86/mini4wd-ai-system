"""Integrated Battery operation tab.

The top-level window owns the BatterySerial connection. This tab exposes
verified 5A commands, live DATA frames, model/Instance assignment and manual
post-measurement result registration.
"""
import sqlite3
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel, QPushButton, QComboBox, QTabWidget, QMessageBox
from battery_system.serial import BatterySerial
from ui.battery_database_ui import BatteryDatabaseDialog

class BatteryTab(QWidget):
    def __init__(self, db_path, transport=None, parent=None):
        super().__init__(parent)
        self.db_path = str(db_path)
        self.transport = transport or BatterySerial()
        self.samples = {1: [], 2: []}
        self.latest_status = {1: "IDLE", 2: "IDLE"}
        self.session_ids = {1: None, 2: None}
        self._build(); self._load_models_and_instances()
        self.timer = QTimer(self); self.timer.setInterval(100); self.timer.timeout.connect(self.poll_serial)
        self._set_controls_enabled(False)

    def _db(self): return sqlite3.connect(self.db_path)

    def _build(self):
        root = QVBoxLayout(self); tabs = QTabWidget(); operation = QWidget(); op = QVBoxLayout(operation)
        status = QGroupBox("STATUS"); sg = QGridLayout(status)
        self.status_labels = {}
        for col, ch in enumerate(("ALL", "CH1", "CH2")):
            self.status_labels[ch] = QLabel(f"{ch}: IDLE"); sg.addWidget(self.status_labels[ch], 0, col)
        op.addWidget(status)

        assignment = QGroupBox("BATTERY INSTANCE ASSIGNMENT"); ar = QVBoxLayout(assignment)
        mr = QHBoxLayout(); self.model = QComboBox(); mr.addWidget(QLabel("Battery Model")); mr.addWidget(self.model); ar.addLayout(mr)
        ir = QHBoxLayout(); self.ch1_instance = QComboBox(); self.ch2_instance = QComboBox(); ir.addWidget(QLabel("CH1 Instance")); ir.addWidget(self.ch1_instance); ir.addWidget(QLabel("CH2 Instance")); ir.addWidget(self.ch2_instance); ar.addLayout(ir)
        self.assignment_status = QLabel("Battery Model / Instanceを読み込み中..."); ar.addWidget(self.assignment_status); op.addWidget(assignment)
        self.ch1_instance.currentIndexChanged.connect(self._validate_instance_assignment); self.ch2_instance.currentIndexChanged.connect(self._validate_instance_assignment)

        controls = QGroupBox("5A DISCHARGE"); cr = QGridLayout(controls)
        for col, name in enumerate(("ALL", "CH1", "CH2")): cr.addWidget(QLabel(name), 0, col)
        self.all_start=QPushButton("START"); self.ch1_start=QPushButton("START"); self.ch2_start=QPushButton("START")
        self.all_stop=QPushButton("STOP"); self.ch1_stop=QPushButton("STOP"); self.ch2_stop=QPushButton("STOP")
        for col, button in enumerate((self.all_start,self.ch1_start,self.ch2_start)): cr.addWidget(button,1,col)
        for col, button in enumerate((self.all_stop,self.ch1_stop,self.ch2_stop)): cr.addWidget(button,2,col)
        self.all_start.clicked.connect(lambda: self.start_channel(None)); self.ch1_start.clicked.connect(lambda: self.start_channel(1)); self.ch2_start.clicked.connect(lambda: self.start_channel(2))
        self.all_stop.clicked.connect(lambda: self.stop_channel(None)); self.ch1_stop.clicked.connect(lambda: self.stop_channel(1)); self.ch2_stop.clicked.connect(lambda: self.stop_channel(2))
        op.addWidget(controls)

        live = QGroupBox("LIVE DATA"); grid = QGridLayout(live); self.live_labels={}
        fields=(("CH1","Voltage"),("CH1","Current"),("CH1","PWM"),("CH1","Time"),("CH2","Voltage"),("CH2","Current"),("CH2","PWM"),("CH2","Time"))
        for i,(channel,field) in enumerate(fields): label=QLabel(f"{channel} {field}: --"); self.live_labels[(channel,field)]=label; grid.addWidget(label,i//4,i%4)
        op.addWidget(live)

        result = QGroupBox("RESULT / MANUAL REGISTRATION"); rr=QGridLayout(result)
        self.result_labels={}
        for row,(key,text) in enumerate((("CH1","CH1 Result"),("CH2","CH2 Result"))):
            self.result_labels[key]=QLabel(f"{text}: no completed measurement"); rr.addWidget(self.result_labels[key],row,0,1,2)
        self.register_result_button=QPushButton("REGISTER RESULT TO DATABASE"); self.register_result_button.setEnabled(False); self.register_result_button.clicked.connect(self.register_results)
        rr.addWidget(self.register_result_button,2,0,1,2); op.addWidget(result)
        op.addWidget(QLabel("実測値は放電中に保持し、終了後に内容を確認してから手動登録します。"))
        tabs.addTab(operation,"5A DISCHARGE")

        db_page=QWidget(); db_layout=QVBoxLayout(db_page); db_button=QPushButton("OPEN BATTERY INSTANCE / RESULT DATABASE"); db_button.clicked.connect(self.open_database); db_layout.addWidget(db_button); db_layout.addStretch(1); tabs.addTab(db_page,"DATABASE"); root.addWidget(tabs)

    def _load_models_and_instances(self):
        self.model.clear(); self.ch1_instance.clear(); self.ch2_instance.clear()
        try:
            with self._db() as db:
                models=db.execute("SELECT battery_model_id,model_code,name FROM battery_model WHERE COALESCE(is_deleted,0)=0 ORDER BY model_code").fetchall()
                instances=db.execute("SELECT bi.instance_id,bi.battery_model_id,bi.nickname,bm.model_code FROM battery_instance bi LEFT JOIN battery_model bm ON bm.battery_model_id=bi.battery_model_id WHERE COALESCE(bi.is_deleted,0)=0 ORDER BY bi.instance_id").fetchall()
            for mid,code,name in models: self.model.addItem(f"{code} / {name}",mid)
            for iid,mid,nickname,code in instances:
                text=f"{iid} / {nickname or code or ''}".rstrip(" /"); self.ch1_instance.addItem(text,iid); self.ch2_instance.addItem(text,iid)
            if not models: self.assignment_status.setText("Battery Model未登録 — DATABASEからModelを登録してください")
            elif not instances: self.assignment_status.setText("Battery Instance未登録 — DATABASEからInstanceを登録してください")
            else: self.assignment_status.setText("Battery Modelを選択し、CH1 / CH2 Instanceを指定してください")
        except sqlite3.Error as exc: self.assignment_status.setText("Battery Model / Instanceを読み込めません"); QMessageBox.warning(self,"Battery",f"Battery Model / Instanceを読み込めません。\n{exc}")

    def _validate_instance_assignment(self):
        a=self.ch1_instance.currentData(); b=self.ch2_instance.currentData()
        if a is not None and b is not None and a==b:
            sender=self.sender(); previous=sender.property("previous_index") if sender is not None else None
            if previous is not None:
                sender.blockSignals(True); sender.setCurrentIndex(int(previous)); sender.blockSignals(False)
            QMessageBox.warning(self,"Battery Instance","同じ測定でCH1とCH2に同じBattery Instanceは指定できません。"); return False
        for combo in (self.ch1_instance,self.ch2_instance): combo.setProperty("previous_index",combo.currentIndex())
        self.assignment_status.setText("CH1 / CH2: Assignment OK" if a is not None and b is not None else "Battery Modelを選択し、CH1 / CH2 Instanceを指定してください")
        return True

    def set_connected(self, connected): self._set_controls_enabled(connected); self.timer.start() if connected else self.timer.stop()
    def _set_controls_enabled(self, enabled):
        valid=self.ch1_instance.currentData() is not None and self.ch2_instance.currentData() is not None and self.ch1_instance.currentData()!=self.ch2_instance.currentData()
        for button in (self.ch1_start,self.ch1_stop,self.ch2_start,self.ch2_stop): button.setEnabled(enabled and valid)
        self.all_start.setEnabled(enabled and valid); self.all_stop.setEnabled(enabled)

    def _status(self, ch, value):
        self.latest_status[ch]=value; self.status_labels[f"CH{ch}"].setText(f"CH{ch}: {value}")
        self.status_labels["ALL"].setText(f"ALL: {self.latest_status[1]} / {self.latest_status[2]}")

    def start_channel(self, channel):
        if not self.transport.connected or not self._validate_instance_assignment(): return
        if channel in (1,2): self.samples[channel]=[]; self.session_ids[channel]=None
        else:
            self.samples={1:[],2:[]}; self.session_ids={1:None,2:None}
        if not self.transport.start(channel): QMessageBox.warning(self,"Battery","STARTコマンドを送信できませんでした。"); return
        if channel is None: self._status(1,"STARTING"); self._status(2,"STARTING")
        else: self._status(channel,"STARTING")
        self.register_result_button.setEnabled(False)

    def stop_channel(self, channel):
        if not self.transport.connected: return
        if not self.transport.stop(channel): QMessageBox.warning(self,"Battery","STOPコマンドを送信できませんでした。"); return
        if channel is None: self._status(1,"STOPPING"); self._status(2,"STOPPING")
        else: self._status(channel,"STOPPING")

    def poll_serial(self):
        for line in self.transport.read_lines():
            text=line.strip()
            if text.startswith("STATUS"):
                parts=text.split(',')
                try:
                    if len(parts)>=3:
                        self._status(1,parts[1].strip()); self._status(2,parts[2].strip())
                except Exception: pass
                continue
            sample=self.transport.parse_data(text)
            if sample is None: continue
            prefix=f"CH{sample.channel}"; self.samples[sample.channel].append(sample)
            self.live_labels[(prefix,"Voltage")].setText(f"{prefix} Voltage: {sample.voltage:.3f} V"); self.live_labels[(prefix,"Current")].setText(f"{prefix} Current: {sample.current:.3f} A"); self.live_labels[(prefix,"PWM")].setText(f"{prefix} PWM: {sample.pwm}"); self.live_labels[(prefix,"Time")].setText(f"{prefix} Time: {sample.elapsed_sec:.1f} s")
            self.result_labels[prefix].setText(f"{prefix} Result: {len(self.samples[sample.channel])} samples / latest {sample.voltage:.3f} V, {sample.current:.3f} A")
            if self.latest_status[1] in ("STOPPED","IDLE") or self.latest_status[2] in ("STOPPED","IDLE"): self.register_result_button.setEnabled(bool(self.samples[1] or self.samples[2]))

    def register_results(self):
        completed=[]
        for ch in (1,2):
            samples=self.samples[ch]; iid=self.ch1_instance.currentData() if ch==1 else self.ch2_instance.currentData()
            if not samples or not iid: continue
            avg_v=sum(x.voltage for x in samples)/len(samples); avg_i=sum(x.current for x in samples)/len(samples); avg_p=sum(x.voltage*x.current for x in samples)/len(samples); max_i=max(x.current for x in samples); max_p=max(x.voltage*x.current for x in samples); duration=max(x.elapsed_sec for x in samples)-min(x.elapsed_sec for x in samples); cap=sum(x.current for x in samples)*0
            completed.append((ch,iid,len(samples),avg_v,avg_i,avg_p,max_i,max_p,duration,cap))
        if not completed: QMessageBox.warning(self,"Battery Result","登録できる完了測定がありません。"); return
        try:
            with self._db() as db:
                for ch,iid,count,avg_v,avg_i,avg_p,max_i,max_p,duration,cap in completed:
                    cur=db.execute("INSERT INTO measurement_session(instance_id,device_type,device_model,firmware_version,analysis_version,start_datetime,end_datetime,operator,result,notes) VALUES(?,?,?,?,?,?,?,?,?,?)",(iid,"EVALUATION","BATTERY_5A","UNKNOWN","battery-benchmark-v1",None,None,"USER","COMPLETE",f"5A channel CH{ch}; manual registration from integrated UI"))
                    sid=cur.lastrowid
                    db.execute("INSERT INTO battery_benchmark_result(session_id,instance_id,analysis_version,measurement_count,avg_voltage,avg_current,avg_power,max_current,max_power,discharge_time_s,capacity_mah) VALUES(?,?,?,?,?,?,?,?,?,?,?)",(sid,iid,"battery-benchmark-v1",count,avg_v,avg_i,avg_p,max_i,max_p,duration,cap))
                db.commit()
            QMessageBox.information(self,"Battery Result","完了した測定結果をデータベースへ登録しました。")
            self.register_result_button.setEnabled(False)
        except sqlite3.Error as exc: QMessageBox.critical(self,"Battery Result",f"登録できません。\n{exc}")

    def open_database(self):
        dialog=BatteryDatabaseDialog(self.db_path,self); dialog.exec_(); self._load_models_and_instances()
