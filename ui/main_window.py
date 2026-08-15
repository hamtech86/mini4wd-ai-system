"""MOTOR_BREAKIN_V3 operator UI: pre-run -> running -> result."""
from pathlib import Path
import sqlite3
from PyQt5.QtCore import QThread,QTimer,pyqtSignal
from PyQt5.QtWidgets import QApplication,QComboBox,QFormLayout,QGroupBox,QHBoxLayout,QLabel,QMainWindow,QMessageBox,QPushButton,QVBoxLayout,QWidget
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
        super().__init__(); self.breakin_worker=None; self.context=context
        root=Path(__file__).resolve().parent.parent; self.recipe_engine=RecipeEngine(str(root/"config"/"breakin_recipes.yaml")); self.breakin_controller=context.get("breakin_controller") if isinstance(context,dict) else getattr(context,"breakin_controller",None)
        self.timer=QTimer(self); self.timer.setInterval(250); self.timer.timeout.connect(self.refresh_runtime)
        self.setWindowTitle("MINI4WD AI SYSTEM - MOTOR BREAKIN V3"); self.resize(1050,780); self.setMinimumSize(900,680); self.build_ui(); self.load_recipes(); self.load_instances(); self.set_ready()
    def build_ui(self):
        root=QWidget(); main=QVBoxLayout(root); main.setContentsMargins(14,12,14,12); main.setSpacing(9)
        h=QLabel("MOTOR BREAK-IN SYSTEM"); h.setStyleSheet("font-size:26px;font-weight:bold;"); main.addWidget(h)
        # 1: pre-run controls
        pre=QGroupBox("① 駆動前：操作"); pv=QVBoxLayout(pre)
        row=QHBoxLayout(); row.addWidget(QLabel("Motor Instance")); self.instance=QComboBox(); row.addWidget(self.instance,1); self.instance_id=QLabel("ID: --"); row.addWidget(self.instance_id); self.manager=QPushButton("MANAGER"); self.manager.clicked.connect(self.open_manager); row.addWidget(self.manager); pv.addLayout(row)
        row2=QHBoxLayout(); row2.addWidget(QLabel("Recipe")); self.recipe=QComboBox(); self.recipe.currentIndexChanged.connect(self.recipe_changed); row2.addWidget(self.recipe,1); self.start=QPushButton("START BREAK-IN"); self.start.clicked.connect(self.start_run); row2.addWidget(self.start); pv.addLayout(row2)
        self.description=QLabel("-"); self.description.setWordWrap(True); pv.addWidget(self.description); main.addWidget(pre)
        # 2: running
        run=QGroupBox("② 駆動中：プログレス / LIVE DATA"); rv=QVBoxLayout(run)
        self.run_state=QLabel("READY"); self.run_state.setStyleSheet("font-size:20px;font-weight:bold;"); rv.addWidget(self.run_state)
        form=QFormLayout(); self.progress={k:QLabel("--") for k in ("Recipe","Step","Phase","Direction","PWM","Motor Voltage","Current","Elapsed","Remaining")};
        for k,w in self.progress.items(): form.addRow(k,w)
        rv.addLayout(form)
        tr=QHBoxLayout(); self.live={k:QLabel("--") for k in ("Arduino","DIR","PWM","V","A","STATE","TEMP")};
        for k,w in self.live.items(): tr.addWidget(QLabel(k+":")); tr.addWidget(w)
        tr.addStretch(); rv.addLayout(tr)
        stoprow=QHBoxLayout(); self.stop=QPushButton("EMERGENCY STOP"); self.stop.setEnabled(False); self.stop.clicked.connect(self.stop_run); stoprow.addWidget(self.stop); stoprow.addStretch(); rv.addLayout(stoprow); main.addWidget(run)
        # compact recipe detail between running and result
        detail=QGroupBox("SELECTED RECIPE"); df=QFormLayout(detail); self.recipe_detail=QLabel("-"); self.phase_detail=QLabel("-"); self.benchmark_detail=QLabel("-"); df.addRow("Description",self.recipe_detail); df.addRow("Phases",self.phase_detail); df.addRow("Benchmark",self.benchmark_detail); main.addWidget(detail)
        # 3: result
        result=QGroupBox("③ 結果"); rf=QFormLayout(result); self.result={k:QLabel("--") for k in ("Status","Brush Peak","Peak State","Benchmark","Summary")};
        for k,w in self.result.items(): rf.addRow(k,w)
        self.copy=QPushButton("COPY RESULT"); self.copy.setEnabled(False); self.copy.clicked.connect(lambda: QApplication.clipboard().setText("\n".join(f"{k}: {w.text()}" for k,w in self.result.items()))); rf.addRow("",self.copy); main.addWidget(result)
        self.setCentralWidget(root)
    def set_ready(self): self.run_state.setText("READY / CONTROLLER CONNECTED" if self.breakin_controller else "ERROR / CONTROLLER NOT AVAILABLE"); self.refresh_runtime(); self.recipe_changed(0)
    def load_recipes(self):
        self.recipe.clear()
        for n in self.recipe_engine.names(): self.recipe.addItem(n,n)
        self.recipe.addItem("MOTOR BENCHMARK TEST (3V / 30s)",self.BENCHMARK_KEY)
    def load_instances(self):
        self.instance.blockSignals(True); self.instance.clear()
        try:
            db=Path(__file__).resolve().parent.parent/"database"/"mini4wd.db"; c=sqlite3.connect(f"file:{db}?mode=ro",uri=True); rows=c.execute("SELECT instance_id,motor_model_id,serial_number,nickname FROM motor_instance WHERE COALESCE(is_deleted,0)=0 ORDER BY instance_id DESC").fetchall(); c.close()
        except Exception: rows=[]
        for iid,mid,sn,nick in rows:self.instance.addItem(f"{iid} / {nick or sn or 'MODEL '+str(mid)}",iid)
        if not rows:self.instance.addItem("NO ACTIVE MOTOR INSTANCE",None)
        self.instance.blockSignals(False); self.instance.currentIndexChanged.connect(self.instance_changed); self.instance_changed(0)
    def instance_changed(self,i):
        iid=self.instance.itemData(i); self.instance_id.setText(f"ID: {iid}" if iid is not None else "ID: --");
        if self.breakin_controller:self.breakin_controller.selected_instance_id=iid
    def open_manager(self):
        try:
            from motor_system.python.ui.motor_manager_ui import MotorManagerUI
            self.manager_window=MotorManagerUI(); self.manager_window.show(); self.manager_window.raise_(); self.manager_window.activateWindow(); self.manager_window.destroyed.connect(self.load_instances)
        except ImportError: QMessageBox.warning(self,"Manager","Motor Instance Manager is unavailable.")
    def recipe_changed(self,_):
        n=self.recipe.currentData()
        if n==self.BENCHMARK_KEY:self.recipe_detail.setText("3.00 V closed-loop benchmark / 30 s / brush peak measurement"); self.phase_detail.setText("BENCHMARK_3V_TEST → BRUSH PEAK"); self.benchmark_detail.setText("3.00 V / 30 s"); return
        r=self.recipe_engine.get(n) if n else None
        if not r:return
        self.recipe_detail.setText(r.description or "-"); self.phase_detail.setText(" → ".join(p.name for p in r.phases)); b=self.recipe_engine.benchmark(); self.benchmark_detail.setText(f"{b.get('target_voltage',3):.2f} V / {b.get('duration_sec',30)} s")
    def refresh_runtime(self):
        c=self.breakin_controller; s=getattr(c,"serial",None) if c else None; self.live["Arduino"].setText("CONNECTED" if getattr(s,"connected",False) else "DISCONNECTED"); m=getattr(getattr(c,"measurement_manager",None),"last_measurement",None) if c else None
        vals={"DIR":getattr(m,"direction",getattr(s,"direction","--")) if m else getattr(s,"direction","--"),"PWM":getattr(m,"pwm",getattr(s,"last_pwm",0)) if m else getattr(s,"last_pwm",0),"V":f"{float(getattr(m,'motor_voltage',0)):.2f} V" if m else "--","A":f"{float(getattr(m,'current_avg',0)):.3f} A" if m else "--","STATE":getattr(m,"state","NO DATA") if m else "NO DATA","TEMP":f"{float(getattr(m,'motor_temperature',0)):.1f} C" if m else "--"};
        for k,v in vals.items():self.live[k].setText(str(v))
        c=self.breakin_controller
        if not c or not getattr(c,"running",False):return
        ph=getattr(c,"current_phase",None)
        if ph is None:return
        e=float(c.phase_elapsed_sec()) if hasattr(c,"phase_elapsed_sec") else 0.; d=float(getattr(ph,"duration_sec",0)); idx=int(getattr(c,"current_phase_index",0)); total=int(getattr(c,"total_phases",0));
        vals={"Recipe":self.recipe.currentText(),"Step":f"{idx+1} / {total}","Phase":getattr(ph,"name","--"),"Direction":getattr(ph,"direction","FWD"),"PWM":getattr(c,"current_pwm",0),"Motor Voltage":self.live["V"].text(),"Current":self.live["A"].text(),"Elapsed":f"{e:.1f} s","Remaining":f"{max(0,d-e):.1f} s"};
        for k,v in vals.items():self.progress[k].setText(str(v))
        self.run_state.setText("RUNNING")
    def start_run(self):
        if not self.breakin_controller:return QMessageBox.warning(self,"Controller","BreakinController is not available.")
        b=self.recipe.currentData()==self.BENCHMARK_KEY; r=None if b else self.recipe_engine.get(self.recipe.currentData())
        if not b and r is None:return
        self.start.setEnabled(False); self.manager.setEnabled(False); self.instance.setEnabled(False); self.recipe.setEnabled(False); self.stop.setEnabled(True); self.result["Status"].setText("RUNNING"); self.run_state.setText("STARTING..."); self.breakin_worker=BreakinWorker(self.breakin_controller,r,b); self.breakin_worker.completed.connect(lambda x:self.complete(x,b)); self.breakin_worker.failed.connect(self.failed); self.breakin_worker.finished.connect(self.finished); self.timer.start(); self.breakin_worker.start()
    def stop_run(self):
        if self.breakin_controller:self.breakin_controller.emergency_stop()
        self.timer.stop(); self.run_state.setText("EMERGENCY STOP"); self.stop.setEnabled(False)
    def complete(self,data,b):
        self.timer.stop(); self.refresh_runtime(); self.run_state.setText("COMPLETE"); self.result["Status"].setText("BENCHMARK COMPLETE" if b else "BREAK-IN COMPLETE"); self.result["Benchmark"].setText("3.00 V / 30 s"); self.result["Summary"].setText(str(data));
        if b:
            peak=getattr(self.breakin_controller,"last_brush_peak_current",None); self.result["Brush Peak"].setText(f"{float(peak):.3f} A" if peak is not None else "--"); self.result["Peak State"].setText("MEASURED / BENCHMARK")
        self.copy.setEnabled(True)
    def failed(self,msg):self.timer.stop();self.run_state.setText("ERROR");self.result["Status"].setText("ERROR");self.result["Summary"].setText(msg)
    def finished(self):self.timer.stop();self.start.setEnabled(True);self.manager.setEnabled(True);self.instance.setEnabled(True);self.recipe.setEnabled(True);self.stop.setEnabled(False);self.breakin_worker=None

def run_app(context=None):
    app=QApplication.instance() or QApplication([]); w=MainWindow(context); w.show(); return app.exec_()
