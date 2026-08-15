"""MOTOR_BREAKIN_V3 operator UI: compact portrait layout with vertical scrolling."""
from pathlib import Path
import sqlite3
import uuid
from PyQt5.QtCore import QThread,QTimer,pyqtSignal,Qt
from PyQt5.QtWidgets import QApplication,QComboBox,QGroupBox,QGridLayout,QHBoxLayout,QLabel,QMainWindow,QMessageBox,QPushButton,QScrollArea,QSizePolicy,QVBoxLayout,QWidget
from controllers.recipe_engine import RecipeEngine

class BreakinWorker(QThread):
    completed=pyqtSignal(object); failed=pyqtSignal(str)
    def __init__(self,controller,recipe=None,benchmark=False): super().__init__(); self.controller=controller; self.recipe=recipe; self.benchmark=benchmark
    def run(self):
        try:self.completed.emit(self.controller.benchmark_3v(duration_sec=30) if self.benchmark else self.controller.start(self.recipe))
        except Exception as e:self.failed.emit(str(e))

class MainWindow(QMainWindow):
    BENCHMARK_KEY="__MOTOR_BENCHMARK_TEST__"
    def __init__(self,context=None):
        super().__init__(); self.context=context; self.breakin_worker=None; self.last_result_data=None; self.last_result_benchmark=False; self.database_updated=False; root=Path(__file__).resolve().parent.parent
        self.db_path=root/"database"/"mini4wd.db"; self.recipe_engine=RecipeEngine(str(root/"config"/"breakin_recipes.yaml")); self.breakin_controller=context.get("breakin_controller") if isinstance(context,dict) else getattr(context,"breakin_controller",None)
        self.timer=QTimer(self); self.timer.setInterval(250); self.timer.timeout.connect(self.refresh_runtime)
        self.setWindowTitle("MINI4WD AI SYSTEM - MOTOR BREAKIN V3"); self.resize(700,1080); self.setMinimumSize(620,600); self.build_ui(); self.load_recipes(); self.load_instances(); self.set_ready()
    def build_ui(self):
        outer=QWidget(); outer_layout=QVBoxLayout(outer); outer_layout.setContentsMargins(3,3,3,3)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff); scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn); scroll.setFrameShape(QScrollArea.NoFrame)
        content=QWidget(); content.setMinimumHeight(1300); main=QVBoxLayout(content); main.setContentsMargins(6,5,18,10); main.setSpacing(8)
        head=QHBoxLayout(); h=QLabel("MOTOR BREAK-IN SYSTEM"); h.setStyleSheet("font-size:25px;font-weight:bold;"); head.addWidget(h); head.addStretch(); self.stop=QPushButton("EMERGENCY STOP"); self.stop.setEnabled(False); self.stop.setFixedSize(120,28); self.stop.clicked.connect(self.stop_run); head.addWidget(self.stop); main.addLayout(head)
        pre=QGroupBox("① 駆動前：操作"); pv=QVBoxLayout(pre); pv.setContentsMargins(8,6,8,6)
        r=QHBoxLayout(); r.addWidget(QLabel("MOTOR INSTANCE")); self.instance=QComboBox(); self.instance.setMinimumWidth(0); self.instance.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed); r.addWidget(self.instance,1); self.instance_id=QLabel("ID: --"); self.instance_id.setFixedWidth(55); r.addWidget(self.instance_id); self.manager=QPushButton("INSTANCE MANAGER"); self.manager.setFixedWidth(145); self.manager.clicked.connect(self.open_manager); r.addWidget(self.manager); pv.addLayout(r)
        r=QHBoxLayout(); r.addWidget(QLabel("RECIPE")); self.recipe=QComboBox(); self.recipe.setMinimumWidth(0); self.recipe.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed); r.addWidget(self.recipe,1); self.start=QPushButton("START BREAK-IN"); self.start.setFixedWidth(145); self.start.clicked.connect(self.start_run); r.addWidget(self.start); pv.addLayout(r)
        self.description=QLabel("-"); self.description.setWordWrap(True); pv.addWidget(self.description); main.addWidget(pre)
        run=QGroupBox("② 駆動中：プログレス / LIVE DATA"); rv=QVBoxLayout(run); rv.setContentsMargins(8,6,8,6); self.run_state=QLabel("READY"); self.run_state.setStyleSheet("font-size:22px;font-weight:bold;"); rv.addWidget(self.run_state)
        self.progress={k:QLabel("--") for k in ("STEP","PHASE","DIR","PWM","VOLT","CURRENT","ELAPSED","REMAIN")}; grid=QGridLayout(); grid.setHorizontalSpacing(5); grid.setVerticalSpacing(5)
        for i,k in enumerate(self.progress):
            box=QGroupBox(k); q=QVBoxLayout(box); q.setContentsMargins(5,4,5,4); self.progress[k].setStyleSheet("font-size:14px;font-weight:bold;"); self.progress[k].setAlignment(Qt.AlignCenter); self.progress[k].setMinimumHeight(34); q.addWidget(self.progress[k]); grid.addWidget(box,i//4,i%4)
        rv.addLayout(grid)
        livegrid=QGridLayout(); livegrid.setHorizontalSpacing(8); livegrid.setVerticalSpacing(4); self.live={k:QLabel("--") for k in ("Arduino","DIR","PWM","V","A","STATE","TEMP")}
        for i,(k,w) in enumerate(self.live.items()): livegrid.addWidget(QLabel(k+":"),i//4*2,i%4*2); livegrid.addWidget(w,i//4*2,i%4*2+1)
        rv.addLayout(livegrid); main.addWidget(run)
        detail=QGroupBox("SELECTED RECIPE"); r=QVBoxLayout(detail); r.setContentsMargins(8,5,8,5); line=QHBoxLayout(); self.recipe_detail=QLabel("-"); self.benchmark_detail=QLabel("-"); line.addWidget(QLabel("Description:")); line.addWidget(self.recipe_detail,1); line.addWidget(QLabel("Benchmark:")); line.addWidget(self.benchmark_detail,1); r.addLayout(line); line=QHBoxLayout(); self.phase_detail=QLabel("-"); line.addWidget(QLabel("Phases:")); line.addWidget(self.phase_detail,1); r.addLayout(line); main.addWidget(detail)
        result=QGroupBox("③ 結果"); rv=QVBoxLayout(result); rv.setContentsMargins(8,6,8,6); self.result={k:QLabel("--") for k in ("STATUS","BRUSH PEAK","PEAK STATE","BENCHMARK","SUMMARY")}; grid=QGridLayout(); grid.setHorizontalSpacing(5); grid.setVerticalSpacing(5)
        for i,k in enumerate(self.result):
            box=QGroupBox(k); q=QVBoxLayout(box); q.setContentsMargins(5,4,5,4); self.result[k].setStyleSheet("font-size:14px;font-weight:bold;"); self.result[k].setWordWrap(True); self.result[k].setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Preferred); q.addWidget(self.result[k]); grid.addWidget(box,0 if i<3 else 1,i if i<3 else i-3)
        rv.addLayout(grid); buttons=QHBoxLayout(); self.copy=QPushButton("COPY RESULT"); self.copy.setEnabled(False); self.copy.setMinimumHeight(36); self.copy.clicked.connect(self.copy_result); buttons.addWidget(self.copy); self.update_db=QPushButton("UPDATE DATABASE"); self.update_db.setEnabled(False); self.update_db.setMinimumHeight(36); self.update_db.clicked.connect(self.update_database); buttons.addWidget(self.update_db); rv.addLayout(buttons); self.database_status=QLabel("DATABASE: NOT UPDATED"); self.database_status.setWordWrap(True); rv.addWidget(self.database_status); main.addWidget(result)
        scroll.setWidget(content); outer_layout.addWidget(scroll); self.setCentralWidget(outer)
    def set_ready(self): self.run_state.setText("READY / CONTROLLER CONNECTED" if self.breakin_controller else "ERROR / CONTROLLER NOT AVAILABLE"); self.refresh_runtime(); self.recipe_changed(0)
    def load_recipes(self):
        self.recipe.clear()
        for n in self.recipe_engine.names(): self.recipe.addItem(n,n)
        self.recipe.addItem("MOTOR BENCHMARK TEST (3V / 30s)",self.BENCHMARK_KEY)
    def load_instances(self):
        self.instance.blockSignals(True); self.instance.clear()
        try:
            db=self.db_path; c=sqlite3.connect(f"file:{db}?mode=ro",uri=True); rows=c.execute("SELECT mi.instance_id,mi.motor_model_id,mi.serial_number,mi.nickname,mm.name,mm.model_code FROM motor_instance mi LEFT JOIN motor_model mm ON mm.motor_model_id=mi.motor_model_id WHERE COALESCE(mi.is_deleted,0)=0 ORDER BY mi.instance_id DESC").fetchall(); c.close()
        except Exception: rows=[]
        for iid,mid,sn,nick,mname,mcode in rows:
            model=f"{mname} ({mcode})" if mname and mcode else (mname or mcode or f"MODEL {mid}")
            self.instance.addItem(f"{iid} / {model} / {nick or sn or ''}".rstrip(" /"),iid)
        if not rows:self.instance.addItem("NO ACTIVE MOTOR INSTANCE",None)
        self.instance.blockSignals(False); self.instance.currentIndexChanged.connect(self.instance_changed); self.instance_changed(0)
    def instance_changed(self,i):
        iid=self.instance.itemData(i); self.instance_id.setText(f"ID: {iid}" if iid is not None else "ID: --")
        if self.breakin_controller:self.breakin_controller.selected_instance_id=iid
    def open_manager(self):
        try:
            from motor_system.python.ui.motor_manager_ui import MotorManagerUI
            self.manager_window=MotorManagerUI(); self.manager_window.setAttribute(Qt.WA_DeleteOnClose,True); self.manager_window.destroyed.connect(self.load_instances); self.manager_window.show(); self.manager_window.raise_(); self.manager_window.activateWindow()
        except Exception as e: QMessageBox.critical(self,"Instance Manager",f"Motor Instance Managerを起動できません。\n{type(e).__name__}: {e}")
    def recipe_changed(self,_):
        n=self.recipe.currentData()
        if n==self.BENCHMARK_KEY:self.recipe_detail.setText("3.00 V closed-loop benchmark / 30 s / brush peak measurement"); self.phase_detail.setText("BENCHMARK_3V_TEST → BRUSH PEAK"); self.benchmark_detail.setText("3.00 V / 30 s"); return
        r=self.recipe_engine.get(n) if n else None
        if not r:return
        self.recipe_detail.setText(r.description or "-"); self.phase_detail.setText(" → ".join(p.name for p in r.phases)); b=self.recipe_engine.benchmark(); self.benchmark_detail.setText(f"{b.get('target_voltage',3):.2f} V / {b.get('duration_sec',30)} s")
    def refresh_runtime(self):
        c=self.breakin_controller; s=getattr(c,"serial",None) if c else None; self.live["Arduino"].setText("CONNECTED" if getattr(s,"connected",False) else "DISCONNECTED"); m=getattr(getattr(c,"measurement_manager",None),"last_measurement",None) if c else None
        vals={"DIR":getattr(m,"direction",getattr(s,"direction","--")) if m else getattr(s,"direction","--"),"PWM":getattr(m,"pwm",getattr(s,"last_pwm",0)) if m else getattr(s,"last_pwm",0),"V":f"{float(getattr(m,'motor_voltage',0)):.2f} V" if m else "--","A":f"{float(getattr(m,'current_avg',0)):.3f} A" if m else "--","STATE":getattr(m,"state","NO DATA") if m else "NO DATA","TEMP":f"{float(getattr(m,'motor_temperature',0)):.1f} C" if m else "--"}
        for k,v in vals.items():self.live[k].setText(str(v))
        if not c or not getattr(c,"running",False):return
        ph=getattr(c,"current_phase",None)
        if ph is None:return
        e=float(c.phase_elapsed_sec()) if hasattr(c,"phase_elapsed_sec") else 0.; d=float(getattr(ph,"duration_sec",0)); idx=int(getattr(c,"current_phase_index",0)); total=int(getattr(c,"total_phases",0)); vals={"STEP":f"{idx+1} / {total}","PHASE":getattr(ph,"name","--"),"DIR":getattr(ph,"direction","FWD"),"PWM":getattr(c,"current_pwm",0),"VOLT":self.live["V"].text(),"CURRENT":self.live["A"].text(),"ELAPSED":f"{e:.1f} s","REMAIN":f"{max(0,d-e):.1f} s"}
        for k,v in vals.items():self.progress[k].setText(str(v))
        self.run_state.setText("RUNNING")
    def start_run(self):
        if not self.breakin_controller:return QMessageBox.warning(self,"Controller","BreakinController is not available.")
        b=self.recipe.currentData()==self.BENCHMARK_KEY; r=None if b else self.recipe_engine.get(self.recipe.currentData())
        if not b and r is None:return
        self.database_updated=False; self.last_result_data=None; self.last_result_benchmark=False; self.database_status.setText("DATABASE: NOT UPDATED"); self.update_db.setEnabled(False)
        self.start.setEnabled(False); self.manager.setEnabled(False); self.instance.setEnabled(False); self.recipe.setEnabled(False); self.stop.setEnabled(True); self.result["STATUS"].setText("RUNNING"); self.run_state.setText("STARTING..."); self.breakin_worker=BreakinWorker(self.breakin_controller,r,b); self.breakin_worker.completed.connect(lambda x:self.complete(x,b)); self.breakin_worker.failed.connect(self.failed); self.breakin_worker.finished.connect(self.finished); self.timer.start(); self.breakin_worker.start()
    def stop_run(self):
        if self.breakin_controller:self.breakin_controller.emergency_stop()
        self.timer.stop(); self.run_state.setText("EMERGENCY STOP"); self.stop.setEnabled(False); self.update_db.setEnabled(False)
    def _benchmark_summary(self,data):
        if data is None:return "30秒測定完了"
        if isinstance(data,dict):
            for key in ("summary","message","result","status"):
                value=data.get(key)
                if isinstance(value,str) and value.strip():return value.strip()
            elapsed=data.get("elapsed_sec",data.get("duration_sec"))
            if elapsed is not None:return f"ベンチマーク測定完了 / {float(elapsed):.1f} s"
            return "ベンチマーク測定完了"
        return "ベンチマーク測定完了"
    def _benchmark_value(self,data,*keys):
        if isinstance(data,dict):
            for key in keys:
                if key in data and data[key] is not None:
                    try:return float(data[key])
                    except (TypeError,ValueError):pass
        for key in keys:
            value=getattr(data,key,None)
            if value is not None:
                try:return float(value)
                except (TypeError,ValueError):pass
        return None
    def complete(self,data,b):
        self.timer.stop(); self.refresh_runtime(); self.run_state.setText("COMPLETE"); self.last_result_data=data; self.last_result_benchmark=b; self.database_updated=False; self.result["STATUS"].setText("BENCHMARK COMPLETE" if b else "BREAK-IN COMPLETE")
        if b:
            peak=self._benchmark_value(data,"brush_peak_current","peak_current","peak_current_a","max_current","current_peak")
            if peak is None: peak=getattr(self.breakin_controller,"last_brush_peak_current",None)
            self.result["BRUSH PEAK"].setText(f"{peak:.3f} A" if peak is not None else "NOT RECORDED"); self.result["PEAK STATE"].setText("MEASURED / BENCHMARK" if peak is not None else "NO PEAK DATA")
            voltage=self._benchmark_value(data,"target_voltage","benchmark_voltage","voltage"); duration=self._benchmark_value(data,"duration_sec","elapsed_sec","elapsed"); vtxt=f"{voltage:.2f} V" if voltage is not None else "3.00 V"; dtxt=f"{duration:.0f} s" if duration is not None else "30 s"
            self.result["BENCHMARK"].setText(f"{vtxt} / {dtxt}"); self.result["SUMMARY"].setText(self._benchmark_summary(data))
        else:
            self.result["BENCHMARK"].setText("--"); self.result["SUMMARY"].setText("ブレイクイン完了")
        self.copy.setEnabled(True); self.update_db.setEnabled(self.instance.itemData(self.instance.currentIndex()) is not None and self.result["STATUS"].text() in ("BENCHMARK COMPLETE","BREAK-IN COMPLETE")); self.database_status.setText("DATABASE: NOT UPDATED / 結果確認後に更新")
    def failed(self,msg):self.timer.stop();self.run_state.setText("ERROR");self.result["STATUS"].setText("ERROR");self.result["SUMMARY"].setText(msg);self.copy.setEnabled(True);self.update_db.setEnabled(False);self.database_status.setText("DATABASE: NOT UPDATED / ERROR")
    def finished(self):self.timer.stop();self.start.setEnabled(True);self.manager.setEnabled(True);self.instance.setEnabled(True);self.recipe.setEnabled(True);self.stop.setEnabled(False);self.breakin_worker=None
    def copy_result(self):
        text="\n".join(f"{k}: {w.text()}" for k,w in self.result.items()); QApplication.clipboard().setText(text); self.copy.setText("COPIED")
    def update_database(self):
        if self.database_updated:return
        iid=self.instance.itemData(self.instance.currentIndex())
        status=self.result["STATUS"].text()
        if iid is None or status not in ("BENCHMARK COMPLETE","BREAK-IN COMPLETE"):
            QMessageBox.warning(self,"Database","完了した正常結果とMotor Instanceを確認してから更新してください。"); return
        if QMessageBox.question(self,"Database Update",f"この結果をMotor Instance #{iid}へ登録しますか？",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        session_id=str(uuid.uuid4()); now=None
        conn=None
        try:
            conn=sqlite3.connect(self.db_path); conn.execute("PRAGMA foreign_keys=ON")
            import datetime; now=datetime.datetime.now().isoformat(timespec="seconds")
            notes=f"Recipe={self.recipe.currentData()}; Status={status}; Summary={self.result['SUMMARY'].text()}"
            conn.execute("INSERT INTO measurement_session (session_id,measurement_type,status,start_time,end_time,measurement_count,operator,notes,schema_version,firmware_version) VALUES (?,?,?,?,?,?,?,?,?,?)",(session_id,"BREAKIN","FINISHED",now,now,1,"USER",notes,"1.0","MOTOR_BREAKIN_V3"))
            peak=self._benchmark_value(self.last_result_data,"brush_peak_current","peak_current","peak_current_a","max_current","current_peak")
            if peak is None: peak=getattr(self.breakin_controller,"last_brush_peak_current",None)
            voltage=self._benchmark_value(self.last_result_data,"target_voltage","benchmark_voltage","voltage") or (3.0 if self.last_result_benchmark else None)
            duration=self._benchmark_value(self.last_result_data,"duration_sec","elapsed_sec","elapsed") or (30.0 if self.last_result_benchmark else None)
            conn.execute("INSERT INTO measurement (session_id,record_type,device_model,instance_id,elapsed_time,motor_voltage,pwm,direction,state,current_avg,peak_current,brush_peak_current,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",(session_id,"BENCHMARK" if self.last_result_benchmark else "BREAKIN", "MOTOR_BREAKIN_V3",str(iid),duration,None,None,self.live["DIR"].text(),status,None,peak,peak,now))
            conn.commit(); self.database_updated=True; self.update_db.setEnabled(False); self.database_status.setText(f"DATABASE: UPDATED ✓ / Instance #{iid} / Session {session_id}")
        except Exception as e:
            if conn:conn.rollback()
            QMessageBox.critical(self,"Database Update Error",f"DB更新に失敗しました。\n{type(e).__name__}: {e}"); self.database_status.setText("DATABASE: UPDATE FAILED / DBは確定していません")
        finally:
            if conn:conn.close()

def run_app(context=None):
    app=QApplication.instance() or QApplication([]); w=MainWindow(context); w.show(); return app.exec_()
