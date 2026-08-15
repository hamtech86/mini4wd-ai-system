"""MOTOR_BREAKIN_V3 main window.

Integrated operator UI for break-in, benchmark, motor-instance selection,
and live telemetry. Execution remains in BreakinController/RecipeEngine.
"""

from pathlib import Path

from PyQt5.QtCore import QThread, QTimer, pyqtSignal
from PyQt5.QtWidgets import QApplication, QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QListWidget, QMainWindow, QMessageBox, QPushButton, QVBoxLayout, QWidget

from controllers.recipe_engine import RecipeEngine


class BreakinWorker(QThread):
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, controller, recipe=None, benchmark=False):
        super().__init__()
        self.controller = controller
        self.recipe = recipe
        self.benchmark = benchmark

    def run(self):
        try:
            result = self.controller.benchmark_3v(duration_sec=30) if self.benchmark else self.controller.start(self.recipe)
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    BENCHMARK_KEY = "__MOTOR_BENCHMARK_TEST__"
    BENCHMARK_VEHICLE_WEIGHT_G = 130.0
    BENCHMARK_TIRE_DIAMETER_MM = 24.0
    BENCHMARK_GEAR_RATIO = 3.5

    def __init__(self, context=None):
        super().__init__()
        self.context = context
        self.breakin_worker = None
        self.recipe_engine = RecipeEngine(str(Path(__file__).resolve().parent.parent / "config" / "breakin_recipes.yaml"))
        self.breakin_controller = context.get("breakin_controller") if isinstance(context, dict) else getattr(context, "breakin_controller", None)
        self.progress_timer = QTimer(self)
        self.progress_timer.setInterval(250)
        self.progress_timer.timeout.connect(self._update_progress)
        self.setWindowTitle("MINI4WD AI SYSTEM - MOTOR BREAKIN V3")
        self.resize(1000, 820)
        self._build_ui()
        self._load_recipes()
        self._set_ready_state()

    def _build_ui(self):
        root = QWidget(); main = QVBoxLayout(root)
        title = QLabel("MOTOR BREAK-IN SYSTEM"); title.setStyleSheet("font-size:22px;font-weight:bold;"); main.addWidget(title)
        self.status = QLabel("READY"); self.status.setStyleSheet("font-size:16px;font-weight:bold;"); main.addWidget(self.status)

        instance_box = QGroupBox("MOTOR INSTANCE"); il = QHBoxLayout(instance_box)
        self.instance_selector = QComboBox(); self.instance_id = QLabel("--"); self.manager_button = QPushButton("MANAGER")
        self.manager_button.clicked.connect(self.open_instance_manager)
        f = QFormLayout(); f.addRow("Instance", self.instance_selector); f.addRow("Selected ID", self.instance_id); il.addLayout(f, 1); il.addWidget(self.manager_button); main.addWidget(instance_box)

        progress_box = QGroupBox("LIVE BREAK-IN PROGRESS"); p = QFormLayout(progress_box)
        self.progress_recipe=QLabel("--"); self.progress_step=QLabel("--"); self.progress_phase=QLabel("--"); self.progress_direction=QLabel("--"); self.progress_pwm=QLabel("--"); self.progress_elapsed=QLabel("--"); self.progress_remaining=QLabel("--"); self.progress_next=QLabel("--"); self.progress_state=QLabel("READY")
        for n,w in (("Recipe",self.progress_recipe),("Step",self.progress_step),("Current Phase",self.progress_phase),("Direction",self.progress_direction),("PWM",self.progress_pwm),("Elapsed",self.progress_elapsed),("Remaining",self.progress_remaining),("Next",self.progress_next),("Execution",self.progress_state)): p.addRow(n,w)
        main.addWidget(progress_box)

        tele = QGroupBox("LIVE ARDUINO / SENSOR"); tl=QHBoxLayout(tele); self.telemetry={}
        for key in ("Arduino","DIR","PWM","V","A","STATE","TEMP"):
            tl.addWidget(QLabel(key+":")); self.telemetry[key]=QLabel("--"); tl.addWidget(self.telemetry[key])
        tl.addStretch(1); main.addWidget(tele)

        content=QHBoxLayout(); rb=QGroupBox("BREAK-IN / BENCHMARK"); rl=QVBoxLayout(rb)
        self.recipe_selector=QComboBox(); self.recipe_selector.currentIndexChanged.connect(self._recipe_changed); rl.addWidget(self.recipe_selector)
        self.description=QLabel("-"); self.description.setWordWrap(True); rl.addWidget(self.description)
        self.phase_list=QListWidget(); rl.addWidget(self.phase_list); content.addWidget(rb,2)
        info=QGroupBox("RECIPE / BENCHMARK"); inf=QFormLayout(info)
        self.info_widgets={k:QLabel("-") for k in ("Brush","Objective","Target RPM","Torque Priority","Benchmark","Vehicle Weight","Tire Diameter","Gear Ratio","Safety","Brush Peak","Peak State")}
        for k,w in self.info_widgets.items(): inf.addRow(k,w)
        content.addWidget(info,1); main.addLayout(content)

        result=QGroupBox("RESULT"); rf=QFormLayout(result)
        self.result_display=QLabel("--"); self.rpm_display=QLabel("--"); self.torque_display=QLabel("--"); self.lifecycle_display=QLabel("--"); self.benchmark_detail=QLabel("--"); self.benchmark_detail.setWordWrap(True)
        for k,w in (("Summary",self.result_display),("Estimated RPM",self.rpm_display),("Estimated Torque",self.torque_display),("Brush Lifecycle",self.lifecycle_display),("Benchmark Detail",self.benchmark_detail)): rf.addRow(k,w)
        main.addWidget(result)

        controls=QHBoxLayout(); self.start_button=QPushButton("START BREAK-IN"); self.stop_button=QPushButton("EMERGENCY STOP"); self.copy_button=QPushButton("COPY BENCHMARK RESULT"); self.stop_button.setEnabled(False); self.copy_button.setEnabled(False)
        self.start_button.clicked.connect(self.start_breakin); self.stop_button.clicked.connect(self.stop_breakin); self.copy_button.clicked.connect(self.copy_benchmark_result)
        for w in (self.start_button,self.stop_button,self.copy_button): controls.addWidget(w)
        main.addLayout(controls); self.setCentralWidget(root)

    def _load_recipes(self):
        self.recipe_selector.clear()
        for name in self.recipe_engine.names(): self.recipe_selector.addItem(name,name)
        self.recipe_selector.addItem("MOTOR BENCHMARK TEST (3V / 30s)", self.BENCHMARK_KEY)

    def _set_ready_state(self):
        self.status.setText("READY / CONTROLLER CONNECTED" if self.breakin_controller else "ERROR / CONTROLLER NOT AVAILABLE")
        self.load_instances(); self._update_telemetry()
        if self.recipe_selector.count(): self._recipe_changed(0)

    def load_instances(self):
        self.instance_selector.clear()
        try:
            import sqlite3
            db=Path(__file__).resolve().parent.parent/"database"/"mini4wd.db"
            con=sqlite3.connect(f"file:{db}?mode=ro",uri=True)
            rows=con.execute("SELECT instance_id,motor_model_id,serial_number,nickname FROM motor_instance WHERE COALESCE(is_deleted,0)=0 ORDER BY instance_id DESC").fetchall(); con.close()
        except Exception:
            rows=[]
        for iid,mid,sn,nick in rows: self.instance_selector.addItem(f"{iid} / {nick or sn or 'MODEL '+str(mid)} / MODEL {mid}",iid)
        if not rows: self.instance_selector.addItem("NO ACTIVE MOTOR INSTANCE",None)
        self.instance_selector.currentIndexChanged.connect(self._instance_changed)
        if rows: self._instance_changed(0)

    def _instance_changed(self,index):
        iid=self.instance_selector.itemData(index); self.instance_id.setText(str(iid) if iid is not None else "--")
        if self.breakin_controller is not None: self.breakin_controller.selected_instance_id=iid

    def open_instance_manager(self):
        try:
            from motor_system.python.ui.motor_manager_ui import MotorManagerUI
        except ImportError:
            QMessageBox.warning(self,"Manager","Motor Instance Manager is unavailable."); return
        self._manager_window=MotorManagerUI(); self._manager_window.show(); self._manager_window.raise_(); self._manager_window.activateWindow(); self._manager_window.destroyed.connect(self.load_instances)

    def selected_recipe(self):
        name=self.recipe_selector.currentData(); return None if not name or name==self.BENCHMARK_KEY else self.recipe_engine.get(name)

    def _recipe_changed(self,_index):
        name=self.recipe_selector.currentData()
        if name==self.BENCHMARK_KEY:
            self.description.setText("Standalone 3 V benchmark. Closed-loop 3.00 V for 30 seconds. Used to measure brush peak and post-break-in motor state.")
            for k,v in (("Brush","UNKNOWN"),("Objective","MEASUREMENT"),("Target RPM","--"),("Torque Priority","0.50"),("Benchmark","3.00 V / 30 s"),("Vehicle Weight","130 g"),("Tire Diameter","24 mm"),("Gear Ratio","3.5:1")): self.info_widgets[k].setText(v)
            self.phase_list.clear(); self.phase_list.addItem("BENCHMARK_3V_TEST: closed-loop 3.00 V / 30s"); self.phase_list.addItem("BRUSH PEAK: MEASURE / STORE"); return
        recipe=self.selected_recipe()
        if recipe is None:return
        self.description.setText(recipe.description or "-"); self.info_widgets["Brush"].setText(recipe.brush); self.info_widgets["Objective"].setText(recipe.objective); self.info_widgets["Target RPM"].setText("--" if recipe.target_rpm is None else f"{recipe.target_rpm:,} rpm"); self.info_widgets["Torque Priority"].setText(f"{recipe.torque_priority:.2f}")
        b=self.recipe_engine.benchmark(); self.info_widgets["Benchmark"].setText(f"{b.get('target_voltage',3.0):.2f} V / {b.get('duration_sec',30)} s")
        self.phase_list.clear()
        for ph in recipe.phases: self.phase_list.addItem(f"{ph.name}: PWM {ph.pwm}, {ph.duration_sec}s" + (f", {ph.control}" if ph.control else ""))

    def _update_telemetry(self):
        c=self.breakin_controller; s=getattr(c,"serial",None) if c else None; self.telemetry["Arduino"].setText("CONNECTED" if getattr(s,"connected",False) else "DISCONNECTED")
        m=getattr(getattr(c,"measurement_manager",None),"last_measurement",None) if c else None
        vals={"DIR":getattr(m,"direction",getattr(s,"direction","--")) if m else getattr(s,"direction","--"),"PWM":getattr(m,"pwm",getattr(s,"last_pwm",0)) if m else getattr(s,"last_pwm",0),"V":f"{float(getattr(m,'motor_voltage',0.0)):.2f} V" if m else "--","A":f"{float(getattr(m,'current_avg',0.0)):.3f} A" if m else "--","STATE":getattr(m,"state","NO DATA") if m else "NO DATA","TEMP":f"{float(getattr(m,'motor_temperature',0.0)):.1f} °C" if m else "--"}
        for k,v in vals.items(): self.telemetry[k].setText(str(v))

    def _update_progress(self):
        self._update_telemetry(); c=self.breakin_controller
        if not c or not getattr(c,"running",False): return
        ph=getattr(c,"current_phase",None)
        if ph is None:return
        idx=int(getattr(c,"current_phase_index",0)); total=int(getattr(c,"total_phases",0)); elapsed=float(c.phase_elapsed_sec()) if hasattr(c,"phase_elapsed_sec") else 0.0; dur=float(getattr(ph,"duration_sec",0.0))
        self.progress_recipe.setText("MOTOR BENCHMARK TEST" if self.recipe_selector.currentData()==self.BENCHMARK_KEY else str(self.recipe_selector.currentData())); self.progress_step.setText(f"{idx+1} / {total}"); self.progress_phase.setText(str(getattr(ph,"name","--"))); self.progress_direction.setText(str(getattr(ph,"direction","FWD"))); self.progress_pwm.setText(str(getattr(c,"current_pwm",0))); self.progress_elapsed.setText(f"{elapsed:.1f} / {dur:.1f} s"); self.progress_remaining.setText(f"{max(0,dur-elapsed):.1f} s"); self.progress_state.setText("RUNNING")

    def start_breakin(self):
        if not self.breakin_controller: QMessageBox.warning(self,"Controller","BreakinController is not available."); return
        if self.breakin_worker and self.breakin_worker.isRunning(): return
        benchmark=self.recipe_selector.currentData()==self.BENCHMARK_KEY; recipe=None if benchmark else self.selected_recipe()
        if not benchmark and recipe is None: QMessageBox.warning(self,"Recipe","No valid recipe is selected."); return
        self.start_button.setEnabled(False); self.stop_button.setEnabled(True); self.recipe_selector.setEnabled(False); self.result_display.setText("RUNNING...")
        self.breakin_worker=BreakinWorker(self.breakin_controller,recipe,benchmark); self.breakin_worker.completed.connect(lambda r:self.on_complete(r,benchmark)); self.breakin_worker.failed.connect(self.on_failed); self.breakin_worker.finished.connect(self.on_finished); self.progress_timer.start(); self.breakin_worker.start()

    def stop_breakin(self):
        if self.breakin_controller:self.breakin_controller.emergency_stop()
        self.progress_timer.stop(); self.status.setText("STOPPED / EMERGENCY STOP"); self.start_button.setEnabled(True); self.stop_button.setEnabled(False); self.recipe_selector.setEnabled(True)

    def on_complete(self,result,benchmark):
        self.progress_timer.stop(); self._update_telemetry(); self.status.setText("MOTOR BENCHMARK COMPLETE" if benchmark else "BREAK-IN COMPLETE / BENCHMARK FINISHED"); self.result_display.setText("COMPLETE")
        if benchmark:
            peak=getattr(self.breakin_controller,"last_brush_peak_current",None); self.info_widgets["Brush Peak"].setText(f"{float(peak):.3f} A" if peak is not None else "--"); self.info_widgets["Peak State"].setText("MEASURED / BENCHMARK"); self.copy_button.setEnabled(True); self.benchmark_detail.setText(str(result))

    def on_failed(self,msg): self.progress_timer.stop(); self.status.setText(f"ERROR / {msg}"); self.result_display.setText("ERROR"); self.benchmark_detail.setText(msg)
    def on_finished(self): self.progress_timer.stop(); self.start_button.setEnabled(True); self.stop_button.setEnabled(False); self.recipe_selector.setEnabled(True); self.breakin_worker=None
    def copy_benchmark_result(self):
        QApplication.clipboard().setText(self.benchmark_detail.text())


def run_app(context=None):
    app=QApplication.instance() or QApplication([]); window=MainWindow(context); window.show(); return app.exec_()
