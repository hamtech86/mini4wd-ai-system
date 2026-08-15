"""Integrated MOTOR_BREAKIN_V3 operator UI."""
from pathlib import Path
import sqlite3
from PyQt5.QtCore import QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import QApplication,QComboBox,QFormLayout,QGroupBox,QHBoxLayout,QLabel,QListWidget,QMainWindow,QMessageBox,QPushButton,QVBoxLayout,QWidget
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
        super().__init__(); self.context=context; self.breakin_worker=None
        self.recipe_engine=RecipeEngine(str(Path(__file__).resolve().parent.parent/"config"/"breakin_recipes.yaml"))
        self.breakin_controller=context.get("breakin_controller") if isinstance(context,dict) else getattr(context,"breakin_controller",None)
        self.progress_timer=QTimer(self); self.progress_timer.setInterval(250); self.progress_timer.timeout.connect(self._update_progress)
        self.setWindowTitle("MINI4WD AI SYSTEM - MOTOR BREAKIN V3"); self.resize(1100,760); self.setMinimumSize(900,650); self._build_ui(); self._load_recipes(); self._set_ready_state()

    def _build_ui(self):
        root=QWidget(); main=QVBoxLayout(root); main.setContentsMargins(10,10,10,10); main.setSpacing(7)
        t=QLabel("MOTOR BREAK-IN SYSTEM"); t.setStyleSheet("font-size:22px;font-weight:bold;"); main.addWidget(t)
        self.status=QLabel("READY"); main.addWidget(self.status)
        ib=QGroupBox("MOTOR INSTANCE"); il=QHBoxLayout(ib); f=QFormLayout(); self.instance_selector=QComboBox(); self.instance_id=QLabel("--"); f.addRow("Instance",self.instance_selector); f.addRow("Selected ID",self.instance_id); il.addLayout(f,1); self.manager_button=QPushButton("MANAGER"); self.manager_button.clicked.connect(self.open_instance_manager); il.addWidget(self.manager_button); main.addWidget(ib)
        pb=QGroupBox("LIVE BREAK-IN PROGRESS"); p=QFormLayout(pb); self.progress={k:QLabel("--") for k in ("Recipe","Step","Phase","Direction","PWM","Elapsed","Remaining","Next","State")};
        for k,w in self.progress.items(): p.addRow(k,w)
        main.addWidget(pb)
        tb=QGroupBox("LIVE ARDUINO / SENSOR"); tl=QHBoxLayout(tb); self.telemetry={};
        for k in ("Arduino","DIR","PWM","V","A","STATE","TEMP"): tl.addWidget(QLabel(k+":")); self.telemetry[k]=QLabel("--"); tl.addWidget(self.telemetry[k])
        tl.addStretch(); main.addWidget(tb)
        body=QHBoxLayout(); rb=QGroupBox("BREAK-IN / BENCHMARK"); rl=QVBoxLayout(rb); self.recipe_selector=QComboBox(); self.recipe_selector.currentIndexChanged.connect(self._recipe_changed); rl.addWidget(self.recipe_selector); self.description=QLabel("-"); self.description.setWordWrap(True); rl.addWidget(self.description); self.phase_list=QListWidget(); rl.addWidget(self.phase_list); body.addWidget(rb,2)
        info=QGroupBox("RECIPE / BENCHMARK"); inf=QFormLayout(info); self.info={k:QLabel("-") for k in ("Brush","Objective","Target RPM","Torque Priority","Benchmark","Vehicle Weight","Tire Diameter","Gear Ratio","Safety","Brush Peak","Peak State")};
        for k,w in self.info.items(): inf.addRow(k,w)
        body.addWidget(info,1); main.addLayout(body,1)
        result=QGroupBox("RESULT"); rf=QFormLayout(result); self.result_display=QLabel("--"); self.benchmark_detail=QLabel("--"); self.benchmark_detail.setWordWrap(True); rf.addRow("Summary",self.result_display); rf.addRow("Benchmark Detail",self.benchmark_detail); main.addWidget(result)
        controls=QHBoxLayout(); self.start_button=QPushButton("START BREAK-IN"); self.stop_button=QPushButton("EMERGENCY STOP"); self.copy_button=QPushButton("COPY BENCHMARK RESULT"); self.stop_button.setEnabled(False); self.copy_button.setEnabled(False); self.start_button.clicked.connect(self.start_breakin); self.stop_button.clicked.connect(self.stop_breakin); self.copy_button.clicked.connect(self.copy_benchmark_result); controls.addWidget(self.start_button); controls.addWidget(self.stop_button); controls.addWidget(self.copy_button); main.addLayout(controls); self.setCentralWidget(root)

    def _load_recipes(self):
        self.recipe_selector.clear()
        for n in self.recipe_engine.names(): self.recipe_selector.addItem(n,n)
        self.recipe_selector.addItem("MOTOR BENCHMARK TEST (3V / 30s)",self.BENCHMARK_KEY)
    def _set_ready_state(self): self.status.setText("READY / CONTROLLER CONNECTED" if self.breakin_controller else "ERROR / CONTROLLER NOT AVAILABLE"); self.load_instances(); self._update_telemetry(); self._recipe_changed(0)
    def load_instances(self):
        self.instance_selector.blockSignals(True); self.instance_selector.clear()
        try:
            db=Path(__file__).resolve().parent.parent/"database"/"mini4wd.db"; c=sqlite3.connect(f"file:{db}?mode=ro",uri=True); rows=c.execute("SELECT instance_id,motor_model_id,serial_number,nickname FROM motor_instance WHERE COALESCE(is_deleted,0)=0 ORDER BY instance_id DESC").fetchall(); c.close()
        except Exception: rows=[]
        for iid,mid,sn,nick in rows:self.instance_selector.addItem(f"{iid} / {nick or sn or 'MODEL '+str(mid)} / MODEL {mid}",iid)
        if not rows:self.instance_selector.addItem("NO ACTIVE MOTOR INSTANCE",None)
        self.instance_selector.blockSignals(False); self.instance_selector.currentIndexChanged.connect(self._instance_changed) if self.instance_selector.receivers(self.instance_selector.currentIndexChanged)>0 else None
        if rows:self._instance_changed(0)
    def _instance_changed(self,i):
        iid=self.instance_selector.itemData(i); self.instance_id.setText(str(iid) if iid is not None else "--");
        if self.breakin_controller:self.breakin_controller.selected_instance_id=iid
    def open_instance_manager(self):
        try:
            from motor_system.python.ui.motor_manager_ui import MotorManagerUI
            self._manager_window=MotorManagerUI(); self._manager_window.show(); self._manager_window.raise_(); self._manager_window.activateWindow(); self._manager_window.destroyed.connect(self.load_instances)
        except ImportError: QMessageBox.warning(self,"Manager","Motor Instance Manager is unavailable.")
    def selected_recipe(self):
        n=self.recipe_selector.currentData(); return None if not n or n==self.BENCHMARK_KEY else self.recipe_engine.get(n)
    def _recipe_changed(self,_):
        n=self.recipe_selector.currentData()
        if n==self.BENCHMARK_KEY:
            self.description.setText("Standalone closed-loop 3.00 V benchmark for 30 seconds. Measures brush peak.")
            for k,v in (("Brush","UNKNOWN"),("Objective","MEASUREMENT"),("Target RPM","--"),("Torque Priority","0.50"),("Benchmark","3.00 V / 30 s"),("Vehicle Weight","130 g"),("Tire Diameter","24 mm"),("Gear Ratio","3.5:1")):self.info[k].setText(v)
            self.phase_list.clear(); self.phase_list.addItem("BENCHMARK_3V_TEST: 3.00 V / 30s"); self.phase_list.addItem("BRUSH PEAK: MEASURE / STORE"); return
        r=self.selected_recipe()
        if not r:return
        self.description.setText(r.description or "-"); self.info["Brush"].setText(r.brush); self.info["Objective"].setText(r.objective); self.info["Target RPM"].setText("--" if r.target_rpm is None else f"{r.target_rpm:,} rpm"); self.info["Torque Priority"].setText(f"{r.torque_priority:.2f}"); b=self.recipe_engine.benchmark(); self.info["Benchmark"].setText(f"{b.get('target_voltage',3):.2f} V / {b.get('duration_sec',30)} s"); self.phase_list.clear();
        for ph in r.phases:self.phase_list.addItem(f"{ph.name}: PWM {ph.pwm}, {ph.duration_sec}s"+(f", {ph.control}" if ph.control else ""))
    def _update_telemetry(self):
        c=self.breakin_controller; s=getattr(c,"serial",None) if c else None; self.telemetry["Arduino"].setText("CONNECTED" if getattr(s,"connected",False) else "DISCONNECTED"); m=getattr(getattr(c,"measurement_manager",None),"last_measurement",None) if c else None
        vals={"DIR":getattr(m,"direction",getattr(s,"direction","--")) if m else getattr(s,"direction","--"),"PWM":getattr(m,"pwm",getattr(s,"last_pwm",0)) if m else getattr(s,"last_pwm",0),"V":f"{float(getattr(m,'motor_voltage',0)):.2f} V" if m else "--","A":f"{float(getattr(m,'current_avg',0)):.3f} A" if m else "--","STATE":getattr(m,"state","NO DATA") if m else "NO DATA","TEMP":f"{float(getattr(m,'motor_temperature',0)):.1f} C" if m else "--"}; [self.telemetry[k].setText(str(v)) for k,v in vals.items()]
    def _update_progress(self):
        self._update_telemetry(); c=self.breakin_controller
        if not c or not getattr(c,"running",False):return
        ph=getattr(c,"current_phase",None)
        if ph is None:return
        idx=int(getattr(c,"current_phase_index",0)); total=int(getattr(c,"total_phases",0)); e=float(c.phase_elapsed_sec()) if hasattr(c,"phase_elapsed_sec") else 0.; d=float(getattr(ph,"duration_sec",0));
        for k,v in (("Recipe","MOTOR BENCHMARK TEST" if self.recipe_selector.currentData()==self.BENCHMARK_KEY else self.recipe_selector.currentData()),("Step",f"{idx+1} / {total}"),("Phase",getattr(ph,"name","--")),("Direction",getattr(ph,"direction","FWD")),("PWM",getattr(c,"current_pwm",0)),("Elapsed",f"{e:.1f} / {d:.1f} s"),("Remaining",f"{max(0,d-e):.1f} s"),("State","RUNNING")):self.progress[k].setText(str(v))
    def start_breakin(self):
        if not self.breakin_controller:return QMessageBox.warning(self,"Controller","BreakinController is not available.")
        if self.breakin_worker and self.breakin_worker.isRunning():return
        b=self.recipe_selector.currentData()==self.BENCHMARK_KEY; r=None if b else self.selected_recipe()
        if not b and r is None:return QMessageBox.warning(self,"Recipe","No valid recipe is selected.")
        self.start_button.setEnabled(False); self.stop_button.setEnabled(True); self.recipe_selector.setEnabled(False); self.result_display.setText("RUNNING..."); self.breakin_worker=BreakinWorker(self.breakin_controller,r,b); self.breakin_worker.completed.connect(lambda x:self.on_complete(x,b)); self.breakin_worker.failed.connect(self.on_failed); self.breakin_worker.finished.connect(self.on_finished); self.progress_timer.start(); self.breakin_worker.start()
    def stop_breakin(self):
        if self.breakin_controller:self.breakin_controller.emergency_stop()
        self.progress_timer.stop(); self.status.setText("STOPPED / EMERGENCY STOP"); self.start_button.setEnabled(True); self.stop_button.setEnabled(False); self.recipe_selector.setEnabled(True)
    def on_complete(self,result,b):
        self.progress_timer.stop(); self._update_telemetry(); self.status.setText("MOTOR BENCHMARK COMPLETE" if b else "BREAK-IN COMPLETE / BENCHMARK FINISHED"); self.result_display.setText("COMPLETE")
        if b:
            peak=getattr(self.breakin_controller,"last_brush_peak_current",None); self.info["Brush Peak"].setText(f"{float(peak):.3f} A" if peak is not None else "--"); self.info["Peak State"].setText("MEASURED / BENCHMARK"); self.copy_button.setEnabled(True); self.benchmark_detail.setText(str(result))
    def on_failed(self,msg):self.progress_timer.stop();self.status.setText(f"ERROR / {msg}");self.result_display.setText("ERROR");self.benchmark_detail.setText(msg)
    def on_finished(self):self.progress_timer.stop();self.start_button.setEnabled(True);self.stop_button.setEnabled(False);self.recipe_selector.setEnabled(True);self.breakin_worker=None
    def copy_benchmark_result(self):QApplication.clipboard().setText(self.benchmark_detail.text())

def run_app(context=None):
    app=QApplication.instance() or QApplication([]); w=MainWindow(context); w.show(); return app.exec_()
