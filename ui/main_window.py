"""MOTOR_BREAKIN_V3 operator UI."""
from pathlib import Path
import csv
import io
import json
import sqlite3
from datetime import datetime

from PyQt5.QtCore import QThread, QTimer, pyqtSignal, Qt
from PyQt5.QtWidgets import (QApplication, QComboBox, QGroupBox, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QSizePolicy, QVBoxLayout, QWidget)
from controllers.recipe_engine import RecipeEngine


class BreakinWorker(QThread):
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)
    def __init__(self, controller, recipe=None, benchmark=False):
        super().__init__(); self.controller=controller; self.recipe=recipe; self.benchmark=benchmark
    def run(self):
        try:
            result=(self.controller.benchmark_3v(duration_sec=30) if self.benchmark else self.controller.start(self.recipe))
            self.completed.emit(result)
        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class MainWindow(QMainWindow):
    BENCHMARK_KEY="__MOTOR_BENCHMARK_TEST__"
    RAW_LOG_FIELDS=("record_type","device_model","instance_id","session_id","elapsed_time",
        "raw_acs1","raw_acs2","current1","current2","voltage1","voltage2","motor_voltage",
        "pwm","direction","state","current_avg","power","current_ripple","voltage_ripple",
        "peak_power","peak_current","peak_voltage","peak_pwm","brush_peak_current","raw_magnetic",
        "magnetic_level","motor_temperature")

    def __init__(self, context=None):
        super().__init__(); self.context=context; self.breakin_worker=None; self.last_result_data=None
        self.last_result_benchmark=False; self.database_updated=False
        root=Path(__file__).resolve().parent.parent; self.db_path=root/"database"/"mini4wd.db"
        self.recipe_engine=RecipeEngine(str(root/"config"/"breakin_recipes.yaml"))
        self.breakin_controller=(context.get("breakin_controller") if isinstance(context,dict) else getattr(context,"breakin_controller",None))
        self.timer=QTimer(self); self.timer.setInterval(250); self.timer.timeout.connect(self.refresh_runtime)
        self.setWindowTitle("MINI4WD AI SYSTEM - MOTOR BREAKIN V3"); self.resize(700,1080); self.setMinimumSize(620,600)
        self.build_ui(); self.load_recipes(); self.load_instances(); self.set_ready()

    def build_ui(self):
        outer=QWidget(); outer_layout=QVBoxLayout(outer); outer_layout.setContentsMargins(3,3,3,3)
        scroll=QScrollArea(); scroll.setWidgetResizable(True); scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn); scroll.setFrameShape(QScrollArea.NoFrame)
        content=QWidget(); content.setMinimumHeight(1400); main=QVBoxLayout(content); main.setContentsMargins(6,5,18,10); main.setSpacing(8)
        head=QHBoxLayout(); title=QLabel("MOTOR BREAK-IN SYSTEM"); title.setStyleSheet("font-size:25px;font-weight:bold;"); head.addWidget(title); head.addStretch()
        self.stop=QPushButton("EMERGENCY STOP"); self.stop.setEnabled(False); self.stop.setFixedSize(120,28); self.stop.clicked.connect(self.stop_run); head.addWidget(self.stop); main.addLayout(head)
        pre=QGroupBox("① 駆動前：操作"); pv=QVBoxLayout(pre); r=QHBoxLayout(); r.addWidget(QLabel("MOTOR INSTANCE"))
        self.instance=QComboBox(); self.instance.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed); r.addWidget(self.instance,1)
        self.instance_id=QLabel("ID: --"); self.instance_id.setFixedWidth(55); r.addWidget(self.instance_id)
        self.manager=QPushButton("INSTANCE MANAGER"); self.manager.setFixedWidth(145); self.manager.clicked.connect(self.open_manager); r.addWidget(self.manager); pv.addLayout(r)
        r=QHBoxLayout(); r.addWidget(QLabel("RECIPE")); self.recipe=QComboBox(); self.recipe.setSizePolicy(QSizePolicy.Expanding,QSizePolicy.Fixed); self.recipe.currentIndexChanged.connect(self.recipe_changed); r.addWidget(self.recipe,1)
        self.start=QPushButton("START BREAK-IN"); self.start.setFixedWidth(145); self.start.clicked.connect(self.start_run); r.addWidget(self.start); pv.addLayout(r)
        self.description=QLabel("-"); self.description.setWordWrap(True); pv.addWidget(self.description); main.addWidget(pre)
        run=QGroupBox("② 駆動中：プログレス / LIVE DATA"); rv=QVBoxLayout(run); self.run_state=QLabel("READY"); self.run_state.setStyleSheet("font-size:22px;font-weight:bold;"); rv.addWidget(self.run_state)
        self.progress={k:QLabel("--") for k in ("STEP","PHASE","DIR","PWM","VOLT","CURRENT","ELAPSED","REMAIN")}; grid=QGridLayout()
        for i,key in enumerate(self.progress):
            box=QGroupBox(key); q=QVBoxLayout(box); self.progress[key].setStyleSheet("font-size:14px;font-weight:bold;"); self.progress[key].setAlignment(Qt.AlignCenter); self.progress[key].setMinimumHeight(34); q.addWidget(self.progress[key]); grid.addWidget(box,i//4,i%4)
        rv.addLayout(grid); livegrid=QGridLayout(); self.live={k:QLabel("--") for k in ("Arduino","DIR","PWM","RPM","V","A","STATE","TEMP")}
        for i,(key,widget) in enumerate(self.live.items()): livegrid.addWidget(QLabel(key+":"),(i//4)*2,(i%4)*2); livegrid.addWidget(widget,(i//4)*2,(i%4)*2+1)
        rv.addLayout(livegrid); main.addWidget(run)
        detail=QGroupBox("SELECTED RECIPE"); dv=QVBoxLayout(detail); line=QHBoxLayout(); self.recipe_detail=QLabel("-"); self.benchmark_detail=QLabel("-")
        line.addWidget(QLabel("Description:")); line.addWidget(self.recipe_detail,1); line.addWidget(QLabel("Benchmark:")); line.addWidget(self.benchmark_detail,1); dv.addLayout(line); self.phase_detail=QLabel("-"); dv.addWidget(self.phase_detail); main.addWidget(detail)
        result=QGroupBox("③ 結果"); rv=QVBoxLayout(result); self.result={k:QLabel("--") for k in ("STATUS","RPM","BENCHMARK RPM","BRUSH PEAK","VOLTAGE","CURRENT","PWM","DIRECTION","BENCHMARK","SUMMARY")}; grid=QGridLayout()
        for i,key in enumerate(self.result):
            box=QGroupBox(key); q=QVBoxLayout(box); self.result[key].setStyleSheet("font-size:14px;font-weight:bold;"); self.result[key].setWordWrap(True); q.addWidget(self.result[key]); grid.addWidget(box,i//3,i%3)
        rv.addLayout(grid); rpm_line=QHBoxLayout(); rpm_line.addWidget(QLabel("Benchmark RPM入力:")); self.benchmark_rpm_input=QLineEdit(); self.benchmark_rpm_input.setPlaceholderText("任意：基準RPM / 実測RPM"); rpm_line.addWidget(self.benchmark_rpm_input,1); rv.addLayout(rpm_line)
        buttons=QHBoxLayout(); self.copy=QPushButton("COPY RESULT"); self.copy.setEnabled(False); self.copy.setMinimumHeight(36); self.copy.clicked.connect(self.copy_result); buttons.addWidget(self.copy)
        self.copy_raw_log=QPushButton("COPY RAW LOG FOR AI ANALYSIS"); self.copy_raw_log.setEnabled(False); self.copy_raw_log.setMinimumHeight(36); self.copy_raw_log.clicked.connect(self.copy_raw_log_for_ai_analysis); buttons.addWidget(self.copy_raw_log)
        self.update_db=QPushButton("UPDATE DATABASE"); self.update_db.setEnabled(False); self.update_db.setMinimumHeight(36); self.update_db.clicked.connect(self.update_database); buttons.addWidget(self.update_db); rv.addLayout(buttons)
        self.database_status=QLabel("DATABASE: NOT UPDATED"); self.database_status.setWordWrap(True); rv.addWidget(self.database_status); main.addWidget(result); scroll.setWidget(content); outer_layout.addWidget(scroll); self.setCentralWidget(outer)

    def set_ready(self): self.run_state.setText("READY / CONTROLLER CONNECTED" if self.breakin_controller else "ERROR / CONTROLLER NOT AVAILABLE"); self.refresh_runtime(); self.recipe_changed(self.recipe.currentIndex())
    def load_recipes(self):
        self.recipe.clear()
        for name in self.recipe_engine.names(): self.recipe.addItem(name,name)
        self.recipe.addItem("MOTOR BENCHMARK TEST (3V / 30s)",self.BENCHMARK_KEY)
    def load_instances(self):
        self.instance.blockSignals(True); self.instance.clear()
        try:
            conn=sqlite3.connect(f"file:{self.db_path}?mode=ro",uri=True); rows=conn.execute("SELECT mi.instance_id, mi.motor_model_id, mi.serial_number, mi.nickname, mm.name, mm.series FROM motor_instance mi LEFT JOIN motor_model mm ON mm.motor_model_id=mi.motor_model_id WHERE COALESCE(mi.is_deleted,0)=0 ORDER BY mi.instance_id DESC").fetchall(); conn.close()
        except Exception: rows=[]
        for iid,mid,serial,nickname,model_name,model_code in rows:
            model=f"{model_name} ({model_code})" if model_name and model_code else (model_name or model_code or f"MODEL {mid}"); self.instance.addItem(f"{iid} / {model} / {nickname or serial or ''}".rstrip(" /"),iid)
        if not rows: self.instance.addItem("NO ACTIVE MOTOR INSTANCE",None)
        self.instance.blockSignals(False)
        try: self.instance.currentIndexChanged.disconnect(self.instance_changed)
        except TypeError: pass
        self.instance.currentIndexChanged.connect(self.instance_changed); self.instance_changed(0)
    def instance_changed(self,index):
        iid=self.instance.itemData(index); self.instance_id.setText(f"ID: {iid}" if iid is not None else "ID: --")
        if self.breakin_controller: self.breakin_controller.selected_instance_id=iid
    def open_manager(self):
        try:
            from motor_system.python.ui.motor_manager_ui import MotorManagerUI
            self.manager_window=MotorManagerUI(); self.manager_window.setAttribute(Qt.WA_DeleteOnClose,True); self.manager_window.destroyed.connect(self.load_instances); self.manager_window.show(); self.manager_window.raise_(); self.manager_window.activateWindow()
        except Exception as exc: QMessageBox.critical(self,"Instance Manager",f"Motor Instance Managerを起動できません。\n{type(exc).__name__}: {exc}")
    def recipe_changed(self,_):
        name=self.recipe.currentData()
        if name==self.BENCHMARK_KEY:
            self.recipe_detail.setText("3.00 V closed-loop benchmark / 30 s / brush peak measurement"); self.phase_detail.setText("BENCHMARK_3V_TEST → BRUSH PEAK"); self.benchmark_detail.setText("3.00 V / 30 s"); return
        recipe=self.recipe_engine.get(name) if name else None
        if recipe is None: return
        self.recipe_detail.setText(recipe.description or "-"); self.phase_detail.setText("Phases: "+" → ".join(p.name for p in recipe.phases)); benchmark=self.recipe_engine.benchmark(); self.benchmark_detail.setText(f"{benchmark.get('target_voltage',3):.2f} V / {benchmark.get('duration_sec',30)} s")

    @staticmethod
    def _number(obj,*names):
        if isinstance(obj,dict):
            for name in names:
                if obj.get(name) is not None:
                    try: return float(obj[name])
                    except (TypeError,ValueError): pass
        else:
            for name in names:
                value=getattr(obj,name,None)
                if value is not None:
                    try: return float(value)
                    except (TypeError,ValueError): pass
        return None
    def _latest_rpm(self):
        c=self.breakin_controller; m=getattr(getattr(c,"measurement_manager",None),"last_measurement",None) if c else None; value=self._number(m,"rpm","RPM","revolutions_per_minute")
        if value is None and c: value=self._number(c,"last_rpm","rpm")
        return value
    def refresh_runtime(self):
        c=self.breakin_controller; serial=getattr(c,"serial",None) if c else None; m=getattr(getattr(c,"measurement_manager",None),"last_measurement",None) if c else None
        self.live["Arduino"].setText("CONNECTED" if getattr(serial,"connected",False) else "DISCONNECTED"); rpm=self._latest_rpm()
        values={"DIR":getattr(m,"direction",getattr(serial,"direction","--")) if m else getattr(serial,"direction","--"),"PWM":getattr(m,"pwm",getattr(serial,"last_pwm",0)) if m else getattr(serial,"last_pwm",0),"RPM":f"{rpm:.0f}" if rpm is not None else "--","V":f"{float(getattr(m,'motor_voltage',0)):.2f} V" if m else "--","A":f"{float(getattr(m,'current_avg',0)):.3f} A" if m else "--","STATE":getattr(m,"state","NO DATA") if m else "NO DATA","TEMP":f"{float(getattr(m,'motor_temperature',0)):.1f} C" if m else "--"}
        for key,value in values.items(): self.live[key].setText(str(value))
        if not c or not getattr(c,"running",False): return
        phase=getattr(c,"current_phase",None)
        if phase is None: return
        elapsed=float(c.phase_elapsed_sec()) if hasattr(c,"phase_elapsed_sec") else 0.; duration=float(getattr(phase,"duration_sec",0)); index=int(getattr(c,"current_phase_index",0)); total=int(getattr(c,"total_phases",0))
        values={"STEP":f"{index+1} / {total}","PHASE":getattr(phase,"name","--"),"DIR":getattr(phase,"direction","FWD"),"PWM":getattr(c,"current_pwm",0),"VOLT":self.live["V"].text(),"CURRENT":self.live["A"].text(),"ELAPSED":f"{elapsed:.1f} s","REMAIN":f"{max(0,duration-elapsed):.1f} s"}
        for key,value in values.items(): self.progress[key].setText(str(value))
        self.run_state.setText("RUNNING")
    def start_run(self):
        if not self.breakin_controller: QMessageBox.warning(self,"Controller","BreakinController is not available."); return
        benchmark=self.recipe.currentData()==self.BENCHMARK_KEY; recipe=None if benchmark else self.recipe_engine.get(self.recipe.currentData())
        if not benchmark and recipe is None: return
        self.database_updated=False; self.last_result_data=None; self.last_result_benchmark=benchmark; self.database_status.setText("DATABASE: NOT UPDATED"); self.update_db.setEnabled(False); self.copy.setEnabled(False); self.copy_raw_log.setEnabled(False); self.start.setEnabled(False); self.manager.setEnabled(False); self.instance.setEnabled(False); self.recipe.setEnabled(False); self.stop.setEnabled(True); self.result["STATUS"].setText("RUNNING"); self.run_state.setText("STARTING...")
        self.breakin_worker=BreakinWorker(self.breakin_controller,recipe,benchmark); self.breakin_worker.completed.connect(lambda data:self.complete(data,benchmark)); self.breakin_worker.failed.connect(self.failed); self.breakin_worker.finished.connect(self.finished); self.timer.start(); self.breakin_worker.start()
    def stop_run(self):
        if self.breakin_controller: self.breakin_controller.emergency_stop()
        self.timer.stop(); self.run_state.setText("EMERGENCY STOP"); self.stop.setEnabled(False); self.update_db.setEnabled(False); self.copy_raw_log.setEnabled(False)
    def complete(self,data,benchmark):
        self.timer.stop(); self.refresh_runtime(); self.run_state.setText("COMPLETE"); self.last_result_data=data; self.last_result_benchmark=benchmark; self.database_updated=False; self.result["STATUS"].setText("BENCHMARK COMPLETE" if benchmark else "BREAK-IN COMPLETE")
        rpm=self._latest_rpm(); self.result["RPM"].setText(f"{rpm:.0f} rpm" if rpm is not None else "NOT AVAILABLE"); self.result["BENCHMARK RPM"].setText(self.benchmark_rpm_input.text().strip()+" rpm" if self.benchmark_rpm_input.text().strip() else "NOT ENTERED")
        controller_peak=getattr(self.breakin_controller,"last_brush_peak_current",None); peak=self._number(data,"brush_peak_current","peak_current","peak_current_a","max_current","current_peak"); peak=controller_peak if peak is None else peak; self.result["BRUSH PEAK"].setText(f"{peak:.3f} A" if peak is not None else "NOT RECORDED")
        measurement=getattr(getattr(self.breakin_controller,"measurement_manager",None),"last_measurement",None); self.result["VOLTAGE"].setText(f"{float(getattr(measurement,'motor_voltage',0)):.2f} V" if measurement else "--"); self.result["CURRENT"].setText(f"{float(getattr(measurement,'current_avg',0)):.3f} A" if measurement else "--"); self.result["PWM"].setText(str(getattr(measurement,"pwm",getattr(self.breakin_controller,"current_pwm","--"))) if measurement else "--"); self.result["DIRECTION"].setText(str(getattr(measurement,"direction",getattr(self.breakin_controller,"serial",None).direction if getattr(self.breakin_controller,"serial",None) else "--"))); self.result["BENCHMARK"].setText("3.00 V / 30 s" if benchmark else "--"); self.result["SUMMARY"].setText("ベンチマーク測定完了" if benchmark else "ブレイクイン完了")
        self.copy.setEnabled(True); self.copy_raw_log.setEnabled(bool(benchmark and self._benchmark_raw_measurements())); self.update_db.setEnabled(self.instance.currentData() is not None); self.database_status.setText("DATABASE: NOT UPDATED / 結果確認後に更新")
    def failed(self,message):
        self.timer.stop(); self.run_state.setText("ERROR"); self.result["STATUS"].setText("ERROR"); self.result["SUMMARY"].setText(message); self.copy.setEnabled(True); self.copy_raw_log.setEnabled(False); self.update_db.setEnabled(False); self.database_status.setText("DATABASE: NOT UPDATED / ERROR")
    def finished(self):
        self.timer.stop(); self.start.setEnabled(True); self.manager.setEnabled(True); self.instance.setEnabled(True); self.recipe.setEnabled(True); self.stop.setEnabled(False); self.breakin_worker=None
    def copy_result(self):
        QApplication.clipboard().setText("\n".join(f"{key}: {widget.text()}" for key,widget in self.result.items())); self.copy.setText("COPIED")

    @staticmethod
    def _measurement_value(measurement,name,default=""):
        return measurement.get(name,default) if isinstance(measurement,dict) else getattr(measurement,name,default)
    def _benchmark_raw_measurements(self):
        if not self.last_result_benchmark or not self.breakin_controller: return []
        measurements=list(getattr(self.breakin_controller,"measurements",[]) or [])
        return [m for m in measurements if self._measurement_value(m,"record_type","DATA")=="DATA"]
    def copy_raw_log_for_ai_analysis(self):
        if not self.last_result_benchmark: QMessageBox.warning(self,"Raw Log","AI解析用生ログは3V / 30秒の正式ベンチマーク結果のみコピーできます。"); return
        measurements=self._benchmark_raw_measurements()
        if not measurements: QMessageBox.warning(self,"Raw Log","3V / 30秒の正式ベンチマーク生ログがありません。"); return
        output=io.StringIO(newline=""); writer=csv.writer(output,lineterminator="\n"); writer.writerow(self.RAW_LOG_FIELDS); instance_id=self.instance.currentData()
        for measurement in measurements:
            row=[]
            for field in self.RAW_LOG_FIELDS:
                if field=="session_id":
                    value=self._measurement_value(measurement,field,"") or getattr(getattr(self.breakin_controller,"session",None),"session_id","")
                elif field=="instance_id":
                    value=self._measurement_value(measurement,field,instance_id if instance_id is not None else "")
                    if value in (None,"","UNKNOWN") and instance_id is not None: value=instance_id
                else: value=self._measurement_value(measurement,field,"")
                row.append(value)
            writer.writerow(row)
        QApplication.clipboard().setText(output.getvalue()); self.copy_raw_log.setText("COPIED RAW LOG")

    def update_database(self):
        if self.database_updated: return
        instance_id=self.instance.currentData()
        if instance_id is None or self.result["STATUS"].text() not in ("BENCHMARK COMPLETE","BREAK-IN COMPLETE"): QMessageBox.warning(self,"Database","正常完了した結果とMotor Instanceが必要です。"); return
        reply=QMessageBox.question(self,"Database Update",f"Instance #{instance_id} に今回の結果を登録しますか？\n\n{self.result['STATUS'].text()} / {self.result['RPM'].text()}",QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if reply!=QMessageBox.Yes: return
        conn=None
        try:
            measurements=list(getattr(self.breakin_controller,"measurements",[]) or []); now=datetime.now().isoformat(timespec="seconds"); conn=sqlite3.connect(self.db_path); conn.execute("PRAGMA foreign_keys = ON"); cur=conn.cursor()
            def table_info(table): return cur.execute(f"PRAGMA table_info({table})").fetchall()
            def table_columns(table): return {row[1] for row in table_info(table)}
            session_info=table_info("measurement_session"); session_columns={row[1] for row in session_info}
            if not session_columns: raise RuntimeError("measurement_session テーブルが存在しません")
            session_required=[row[1] for row in session_info if row[3] and row[4] is None and not row[5]]
            session_values={"instance_id":int(instance_id),"device_type":"BENCHMARK" if self.last_result_benchmark else "BREAKIN","device_model":None,"firmware_version":"MOTOR_BREAKIN_V3","analysis_version":"1.0","calibration_profile":None,"start_datetime":None,"end_datetime":now,"operator":"USER","result":self.result["STATUS"].text(),"notes":json.dumps({"benchmark_rpm":self.benchmark_rpm_input.text().strip(),"result":{k:v.text() for k,v in self.result.items()}},ensure_ascii=False),"created_at":now,"updated_at":now}
            missing=[name for name in session_required if name not in session_values]
            if missing: raise RuntimeError("measurement_session の必須カラムに対応する値がありません: "+", ".join(missing))
            session_data={k:v for k,v in session_values.items() if k in session_columns and k!="session_id"}; names=list(session_data); cur.execute(f"INSERT INTO measurement ({','.join(names)}) VALUES ({','.join('?' for _ in names)})" if False else f"INSERT INTO measurement_session ({','.join(names)}) VALUES ({','.join('?' for _ in names)})",[session_data[n] for n in names]); db_session_id=cur.lastrowid
            if not db_session_id: raise RuntimeError("measurement_session のsession_id取得に失敗しました")
            measurement_info=table_info("measurement"); measurement_columns={row[1] for row in measurement_info}
            if "session_id" not in measurement_columns: raise RuntimeError("measurement.session_id カラムが存在しません")
            measurement_required=[row[1] for row in measurement_info if row[3] and row[4] is None and not row[5]]
            model_columns=("record_type","device_model","instance_id","elapsed_time","raw_acs1","raw_acs2","current1","current2","voltage1","voltage2","motor_voltage","pwm","direction","state","current_avg","power","current_ripple","voltage_ripple","peak_power","peak_current","peak_voltage","peak_pwm","brush_peak_current","raw_magnetic","magnetic_level","motor_temperature")
            inserted=0
            for measurement in measurements:
                row={"session_id":str(db_session_id)}
                for col in model_columns:
                    if col in measurement_columns: row[col]=measurement.get(col) if isinstance(measurement,dict) else getattr(measurement,col,None)
                if "instance_id" in measurement_columns and row.get("instance_id") is None: row["instance_id"]=str(instance_id)
                missing_measurement=[name for name in measurement_required if name not in row]
                if missing_measurement: raise RuntimeError("measurement の必須カラムに対応する値がありません: "+", ".join(missing_measurement))
                names=list(row); cur.execute(f"INSERT INTO measurement ({','.join(names)}) VALUES ({','.join('?' for _ in names)})",[row[n] for n in names]); inserted+=1
            instance_columns=table_columns("motor_instance")
            if "latest_session_id" in instance_columns: cur.execute("UPDATE motor_instance SET latest_session_id=? WHERE instance_id=?",(db_session_id,int(instance_id)))
            conn.commit(); self.database_updated=True; self.update_db.setEnabled(False); self.database_status.setText(f"DATABASE: UPDATED ✓ / Instance #{instance_id} / Session {db_session_id} / Measurements {inserted}")
        except Exception as exc:
            if conn is not None:
                try: conn.rollback()
                except Exception: pass
            QMessageBox.critical(self,"Database Update Error",f"DB更新に失敗しました。\n{type(exc).__name__}: {exc}"); self.database_status.setText(f"DATABASE: UPDATE FAILED / {type(exc).__name__}: {exc}")
        finally:
            if conn is not None:
                try: conn.close()
                except Exception: pass


def run_app(context=None):
    app=QApplication.instance() or QApplication([]); window=MainWindow(context); window.show(); return app.exec_()
