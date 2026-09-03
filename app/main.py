"""MINI4WD AI SYSTEM / MOTOR_BREAKIN_V3 application entry point."""
import sys
import sqlite3
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication, QMessageBox, QGroupBox, QGridLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget, QTabWidget, QHBoxLayout, QCheckBox, QProgressBar
from loguru import logger
from ui.main_window import MainWindow as BaseMainWindow
from communication.serial_controller import SerialController
from battery_system.serial import BatterySerial
from app.application_builder import ApplicationBuilder
from app.raw_log_paste import install_raw_log_paste_ui
from ui.resume_controls import install_resume_controls, bind_resume_api
from ui.battery_tab_ui import BatteryTab
from controllers.recipe_engine import RecipeEngine
from controllers.sequence_executor import SequenceExecutor
from controllers.breakin_sequence_adapter import BreakinSequenceAdapter
from workers.breakin_worker import BreakinWorker
from analysis.analysis_engine import AnalysisEngine

class MainWindow(BaseMainWindow):
    def __init__(self, context=None):
        super().__init__(context)
        self.analysis_engine=AnalysisEngine(str(PROJECT_ROOT / "config"))
        bind_resume_api(type(self)); install_resume_controls(self); self._extract_motor_page(); self._build_estimated_result_panel()
        install_raw_log_paste_ui(self)
        self.battery_serial_controller = context.get("battery_serial_controller") if context else None
        self._build_recipe_sequence_panel(); self._build_integrated_ui()
        if hasattr(self,"start"): self.start.setText("START SELECTED SEQUENCE")

    def _extract_motor_page(self):
        central=self.centralWidget()
        if central is None:return
        scroll=central.findChild(QScrollArea); self.motor_page=central; self.motor_content=scroll.widget() if scroll is not None else None
        if self.motor_content is None:return
        layout=self.motor_content.layout()
        if layout is None:return
        for i in range(layout.count()):
            item=layout.itemAt(i); widget=item.widget() if item else None
            if widget is not None and widget.objectName()=="legacy_device_connection": layout.removeWidget(widget); widget.setParent(None); widget.deleteLater(); break

    def _build_integrated_ui(self):
        old_central=self.takeCentralWidget() or self.motor_page; root=QWidget(); root_layout=QVBoxLayout(root); root_layout.setContentsMargins(5,5,5,5)
        device_box=QGroupBox("DEVICE CONNECTION"); row=QGridLayout(device_box)
        self.motor_serial_status=QLabel("MOTOR: DISCONNECTED  /dev/ttyACM0"); self.motor_connect=QPushButton("MOTOR CONNECT"); self.motor_disconnect=QPushButton("MOTOR DISCONNECT"); self.motor_disconnect.setEnabled(False)
        self.motor_connect.clicked.connect(self.connect_motor_serial); self.motor_disconnect.clicked.connect(self.disconnect_motor_serial)
        self.battery_serial_status=QLabel("BATTERY: DISCONNECTED  /dev/ttyUSB0"); self.battery_connect=QPushButton("BATTERY CONNECT"); self.battery_disconnect=QPushButton("BATTERY DISCONNECT"); self.battery_disconnect.setEnabled(False)
        self.battery_connect.clicked.connect(self.connect_battery_serial); self.battery_disconnect.clicked.connect(self.disconnect_battery_serial)
        row.addWidget(self.motor_serial_status,0,0); row.addWidget(self.motor_connect,0,1); row.addWidget(self.motor_disconnect,0,2); row.addWidget(self.battery_serial_status,1,0); row.addWidget(self.battery_connect,1,1); row.addWidget(self.battery_disconnect,1,2)
        root_layout.addWidget(device_box); tabs=QTabWidget(); tabs.addTab(old_central,"MOTOR BREAK-IN"); self.battery_tab=BatteryTab(self.db_path,transport=self.battery_serial_controller,parent=self); tabs.addTab(self.battery_tab,"BATTERY"); root_layout.addWidget(tabs,1); self.setCentralWidget(root)

    def _motor_controller(self):
        controller=getattr(self,"serial_controller",None)
        if controller is not None:return controller
        controller=getattr(getattr(self,"breakin_controller",None),"serial",None)
        if controller is not None:return controller
        return getattr(getattr(self,"breakin_controller",None),"serial_controller",None)

    def connect_motor_serial(self):
        controller=self._motor_controller()
        if controller is None: QMessageBox.warning(self,"Motor Connection","Motor serial controller is not available."); return
        if controller.connected:return
        if controller.connect(): self.motor_serial_status.setText("MOTOR: CONNECTED  /dev/ttyACM0 @ 57600"); self.motor_connect.setEnabled(False); self.motor_disconnect.setEnabled(True)
        else:self.motor_serial_status.setText("MOTOR: CONNECTION FAILED  /dev/ttyACM0")

    def disconnect_motor_serial(self):
        controller=self._motor_controller()
        if controller is not None:
            try:
                if controller.connected:controller.stop_breakin()
            except Exception:logger.exception("Failed to stop motor before disconnect")
            try:controller.disconnect()
            except Exception:logger.exception("Failed to disconnect motor serial")
        if hasattr(self,"sequence_executor"):self.sequence_executor.stop("motor_disconnected")
        self.motor_serial_status.setText("MOTOR: DISCONNECTED  /dev/ttyACM0"); self.motor_connect.setEnabled(True); self.motor_disconnect.setEnabled(False)

    def connect_battery_serial(self):
        controller=self.battery_serial_controller
        if controller is None: QMessageBox.warning(self,"Battery Connection","Battery serial controller is not available."); return
        if controller.connected:return
        if not controller.connect():self.battery_serial_status.setText("BATTERY: CONNECTION FAILED  /dev/ttyUSB0");return
        self.battery_serial_status.setText("BATTERY: CONNECTED  /dev/ttyUSB0 @ 57600");self.battery_connect.setEnabled(False);self.battery_disconnect.setEnabled(True);self.battery_tab.set_connected(True)

    def disconnect_battery_serial(self):
        controller=self.battery_serial_controller
        if controller is not None:
            try:controller.stop()
            except Exception:pass
            try:controller.disconnect()
            except Exception:logger.exception("Failed to disconnect battery serial")
        self.battery_serial_status.setText("BATTERY: DISCONNECTED  /dev/ttyUSB0");self.battery_connect.setEnabled(True);self.battery_disconnect.setEnabled(False);self.battery_tab.set_connected(False)

    def _selected_motor_spec(self):
        instance_id=self.instance.currentData() if hasattr(self,"instance") else None
        if instance_id is None:return {}
        try:
            conn=sqlite3.connect(f"file:{self.db_path}?mode=ro",uri=True)
            row=conn.execute("SELECT mm.nominal_voltage,mm.nominal_rpm,mm.nominal_current_ma,mm.nominal_torque_gcm FROM motor_instance mi JOIN motor_model mm ON mm.motor_model_id=mi.motor_model_id WHERE mi.instance_id=?",(int(instance_id),)).fetchone()
            conn.close()
            if not row:return {}
            return {"nominal_voltage":row[0],"nominal_rpm":row[1],"nominal_current_ma":row[2],"nominal_torque_gcm":row[3]}
        except Exception:
            logger.exception("Failed to load motor nominal specification")
            return {}

    def _build_estimated_result_panel(self):
        content=self.motor_content; layout=content.layout() if content is not None else None
        if layout is None:return
        self.estimated_result={"RPM_3V":QLabel("--"),"RPM_28V":QLabel("--"),"TORQUE_3V":QLabel("--"),"TORQUE_28V":QLabel("--"),"WEIGHT":QLabel("--")}
        box=QGroupBox("ESTIMATED PERFORMANCE / 推定値");grid=QGridLayout(box)
        labels=(("3.0V換算 推定RPM","RPM_3V"),("2.8V換算 推定RPM","RPM_28V"),("3.0V換算 推定トルク","TORQUE_3V"),("2.8V換算 推定トルク","TORQUE_28V"),("対応車重（推定）","WEIGHT"))
        for index,(title,key) in enumerate(labels):
            card=QGroupBox(title);card_layout=QGridLayout(card);value=self.estimated_result[key];value.setAlignment(Qt.AlignCenter);value.setStyleSheet("font-size:16px;font-weight:bold;");card_layout.addWidget(value,0,0);grid.addWidget(card,index//2,index%2)
        layout.addWidget(box)

    def _update_estimated_result(self):
        measurement=getattr(getattr(self,"breakin_controller",None),"measurement_manager",None)
        measurement=getattr(measurement,"last_measurement",None)
        if measurement is None:return
        try:
            analysis=self.analysis_engine.analyze(measurement,self._selected_motor_spec())
            performance=analysis.performance
            self.estimated_result["RPM_3V"].setText(f"{performance.estimated_rpm_3v.value:.0f} rpm")
            self.estimated_result["RPM_28V"].setText(f"{performance.estimated_rpm_28v.value:.0f} rpm")
            self.estimated_result["TORQUE_3V"].setText(f"{performance.estimated_torque_3v.value:.2f} g·cm")
            self.estimated_result["TORQUE_28V"].setText(f"{performance.estimated_torque_28v.value:.2f} g·cm")
            self.estimated_result["WEIGHT"].setText(f"{performance.estimated_supported_weight.value:.0f} g")
        except Exception:
            logger.exception("Failed to calculate estimated performance")

    def _build_recipe_sequence_panel(self):
        self.recipe_engine=RecipeEngine();self.sequence_adapter=BreakinSequenceAdapter(self.breakin_controller);self.sequence_executor=SequenceExecutor(adapter=self.sequence_adapter);self.sequence_timer=QTimer(self);self.sequence_timer.setInterval(100);self.sequence_timer.timeout.connect(self._sequence_tick);self.sequence_selected_total=0
        box=QGroupBox("SEQUENCE");root=QVBoxLayout(box);actions=QHBoxLayout();self.sequence_all=QPushButton("全選択");self.sequence_none=QPushButton("全解除");self.sequence_all.clicked.connect(lambda:self._set_sequence_checks(True));self.sequence_none.clicked.connect(lambda:self._set_sequence_checks(False));self.sequence_execute=QPushButton("選択Sequenceを実行");self.sequence_stop=QPushButton("Sequence停止");self.sequence_stop.setEnabled(False);self.sequence_execute.clicked.connect(self._execute_selected_sequences);self.sequence_stop.clicked.connect(self._stop_sequences)
        actions.addWidget(self.sequence_all);actions.addWidget(self.sequence_none);actions.addStretch();actions.addWidget(self.sequence_execute);actions.addWidget(self.sequence_stop);root.addLayout(actions)
        self.sequence_progress=QProgressBar();self.sequence_progress.setRange(0,100);self.sequence_progress.setValue(0);self.sequence_progress.setFormat("Sequence Progress: %p%")
        root.addWidget(self.sequence_progress);self.sequence_status=QLabel("未実行");root.addWidget(self.sequence_status);scroll=QScrollArea();scroll.setWidgetResizable(True);body=QWidget();self.sequence_layout=QVBoxLayout(body);scroll.setWidget(body);root.addWidget(scroll,1);self.sequence_checks=[];layout=self.motor_content.layout() if self.motor_content is not None else None
        if layout is not None:layout.insertWidget(1,box)
        self.recipe.currentIndexChanged.connect(self._recipe_selection_changed)
        self._recipe_selection_changed(self.recipe.currentIndex())

    def _current_recipe_name(self):
        return self.recipe.currentData() if hasattr(self,"recipe") else None

    def _recipe_selection_changed(self,index):
        name=self.recipe.itemData(index) if hasattr(self,"recipe") else None
        if name == self.BENCHMARK_KEY:
            self._load_benchmark_sequence()
            return
        self._load_recipe_sequence(name)

    def _clear_sequence_panel(self,status):
        while self.sequence_layout.count():
            item=self.sequence_layout.takeAt(0);widget=item.widget()
            if widget is not None:widget.deleteLater()
        self.sequence_checks=[];self.sequence_progress.setValue(0);self.sequence_status.setText(status)

    def _load_benchmark_sequence(self):
        self._clear_sequence_panel("Motor Benchmark Test: Sequenceを選択してください")
        check=QCheckBox("01 | BENCHMARK_3V | BENCHMARK | FWD | 3.00 V / 30 s")
        check.setChecked(True)
        self.sequence_layout.addWidget(check)
        self.sequence_checks=[(self.BENCHMARK_KEY,check)]
        self.sequence_layout.addStretch()
        self.sequence_status.setText("Motor Benchmark Test: 1 Sequence")

    def _load_recipe_sequence(self,name):
        recipe=self.recipe_engine.get(name)
        if recipe is None:self._clear_sequence_panel("レシピが見つかりません");return
        while self.sequence_layout.count():
            item=self.sequence_layout.takeAt(0);widget=item.widget()
            if widget is not None:widget.deleteLater()
        self.sequence_checks=[]
        for sequence in recipe.sequences():
            check=QCheckBox(f"{sequence.order:02d} | {sequence.sequence_id} | {sequence.command} | {sequence.direction or '-'} | PWM {sequence.pwm if sequence.pwm is not None else '-'} | {sequence.duration_sec if sequence.duration_sec is not None else '-'}s");check.setChecked(sequence.enabled);self.sequence_layout.addWidget(check);self.sequence_checks.append((sequence.sequence_id,check))
        self.sequence_layout.addStretch();self._update_sequence_highlight(None);self.sequence_progress.setValue(0);self.sequence_status.setText(f"{recipe.name}: {len(self.sequence_checks)} Sequence")

    def _set_sequence_checks(self,checked):
        for _,check in self.sequence_checks:check.setChecked(checked)

    def _update_sequence_highlight(self,active_id):
        for sid,check in self.sequence_checks:check.setStyleSheet("QCheckBox { background: palette(highlight); color: palette(highlighted-text); font-weight: bold; padding: 4px; border-radius: 3px; }" if sid==active_id else "QCheckBox { padding: 4px; }")

    def _update_sequence_progress(self):
        total=self.sequence_selected_total
        if total<=0:self.sequence_progress.setValue(0);return
        completed=sum(1 for result in self.sequence_executor.results if result.status=="COMPLETE" and result.sequence_id in self.sequence_selected_ids)
        value=int(completed*100/total)
        self.sequence_progress.setValue(min(100,value));self.sequence_progress.setFormat(f"Sequence Progress: {completed}/{total}  %p%")

    def _update_sequence_main_ui(self,current):
        if current is None:return
        progress=int(self.sequence_executor.progress());total=max(1,self.sequence_selected_total);completed=sum(1 for result in self.sequence_executor.results if result.status in ("COMPLETE","SKIPPED") and result.sequence_id in self.sequence_selected_ids)
        c=self.breakin_controller;m=getattr(getattr(c,"measurement_manager",None),"last_measurement",None) if c else None
        self.run_state.setText("RUNNING")
        result=self.sequence_executor.results[self.sequence_executor.state.sequence_index] if self.sequence_executor.state is not None and self.sequence_executor.state.sequence_index<len(self.sequence_executor.results) else None
        remaining=self.sequence_executor.remaining_sec()
        elapsed=result.elapsed_sec if result is not None else 0.0
        if hasattr(self,"progress"):
            values={"STEP":f"{min(completed+1,total)} / {total}","PHASE":getattr(current,"sequence_id","--"),"DIR":getattr(current,"direction","FWD"),"PWM":getattr(current,"pwm",0),"VOLT":f"{float(getattr(m,'motor_voltage',0)):.2f} V" if m else "--","CURRENT":f"{float(getattr(m,'current_avg',0)):.3f} A" if m else "--","ELAPSED":f"{elapsed:.1f} s","REMAIN":f"{remaining:.1f} s" if remaining is not None else "条件待ち"}
            for key,value in values.items():
                if key in self.progress:self.progress[key].setText(str(value))
        if hasattr(self,"live"):
            values={"DIR":getattr(current,"direction","FWD"),"PWM":getattr(current,"pwm",0),"RPM":self._latest_rpm() if hasattr(self,"_latest_rpm") else "--","V":f"{float(getattr(m,'motor_voltage',0)):.2f} V" if m else "--","A":f"{float(getattr(m,'current_avg',0)):.3f} A" if m else "--","STATE":"RUNNING","TEMP":f"{float(getattr(m,'motor_temperature',0)):.1f} C" if m else "--","Arduino":"CONNECTED"}
            for key,value in values.items():
                if key in self.live:self.live[key].setText(str(value))
        self.sequence_status.setText(f"実行中: {current.sequence_id}  {progress}%  残り {remaining:.1f}s" if remaining is not None else f"実行中: {current.sequence_id}  {progress}%  条件待ち")

    def _execute_selected_sequences(self):
        name=self._current_recipe_name()
        if name==self.BENCHMARK_KEY:
            enabled_ids={sid for sid,check in self.sequence_checks if check.isChecked()}
            if self.BENCHMARK_KEY not in enabled_ids:
                self.sequence_status.setText("Benchmark Sequenceが選択されていません");return
            self._start_benchmark()
            return
        recipe=self.recipe_engine.get(name)
        if recipe is None:self.sequence_status.setText("レシピが選択されていません");return
        enabled_ids={sid for sid,check in self.sequence_checks if check.isChecked()}
        if not enabled_ids:self.sequence_status.setText("実施するSequenceが選択されていません");return
        controller=self._motor_controller()
        if controller is None or not getattr(controller,"connected",False):QMessageBox.warning(self,"Sequence","先にMOTOR CONNECTを実行してください。");return
        self.sequence_selected_ids=enabled_ids;self.sequence_selected_total=len(enabled_ids);self.sequence_progress.setValue(0);self.sequence_progress.setFormat(f"Sequence Progress: 0/{self.sequence_selected_total}  %p%")
        self.sequence_executor.load_recipe(recipe,enabled_ids=enabled_ids);self.sequence_executor.start();self.sequence_timer.start();self.timer.start();self.sequence_execute.setEnabled(False);self.sequence_stop.setEnabled(True);self.start.setEnabled(False);self.stop.setEnabled(True);self.manager.setEnabled(False);self.instance.setEnabled(False);self.recipe.setEnabled(False);self.update_db.setEnabled(False);self.copy.setEnabled(False);self.result["STATUS"].setText("RUNNING");self.run_state.setText("STARTING...");current=self.sequence_executor.current();self._update_sequence_highlight(current.sequence_id if current else None);self._update_sequence_main_ui(current)

    def _start_benchmark(self):
        if not self.breakin_controller:
            QMessageBox.warning(self,"Controller","BreakinController is not available.");return
        self.database_updated=False;self.last_result_data=None;self.last_result_benchmark=True;self.database_status.setText("DATABASE: NOT UPDATED");self.update_db.setEnabled(False);self.copy.setEnabled(False);self.start.setEnabled(False);self.manager.setEnabled(False);self.instance.setEnabled(False);self.recipe.setEnabled(False);self.stop.setEnabled(True);self.result["STATUS"].setText("RUNNING");self.run_state.setText("STARTING...")
        self.breakin_worker=BreakinWorker(self.breakin_controller,None,True)
        self.breakin_worker.completed.connect(lambda data:self.complete(data,True));self.breakin_worker.failed.connect(self.failed);self.breakin_worker.finished.connect(self.finished);self.timer.start();self.breakin_worker.start()

    def start_run(self):
        self._execute_selected_sequences()

    def complete(self,data,benchmark):
        super().complete(data,benchmark)
        self._update_estimated_result()

    def stop_run(self):
        try:
            if self.breakin_controller:self.breakin_controller.emergency_stop()
        finally:
            self.sequence_timer.stop();self.timer.stop()
            if hasattr(self,"sequence_executor"):self.sequence_executor.stop("emergency_stop")
            self.sequence_execute.setEnabled(True);self.sequence_stop.setEnabled(False);self.stop.setEnabled(False);self.start.setEnabled(True);self.manager.setEnabled(True);self.instance.setEnabled(True);self.recipe.setEnabled(True);self.run_state.setText("EMERGENCY STOP");self.result["STATUS"].setText("EMERGENCY STOP");self.sequence_status.setText("緊急停止");self._update_sequence_highlight(None)

    def _sequence_tick(self):
        try:
            current=self.sequence_executor.execute_current();self._update_sequence_progress()
            if self.sequence_executor.is_complete():
                self.sequence_timer.stop();self.timer.stop();self.sequence_progress.setValue(100);self.sequence_progress.setFormat(f"Sequence Progress: {self.sequence_selected_total}/{self.sequence_selected_total}  100%");self.sequence_execute.setEnabled(True);self.sequence_stop.setEnabled(False);self.stop.setEnabled(False);self._update_sequence_highlight(None)
                try:self.complete({},False)
                except Exception:logger.exception("Failed to populate legacy result cards from Sequence result")
                self.start.setEnabled(True);self.manager.setEnabled(True);self.instance.setEnabled(True);self.recipe.setEnabled(True);self.sequence_status.setText("完了: 100%");return
            self._update_sequence_main_ui(current);self._update_sequence_highlight(current.sequence_id if current else None)
        except Exception as exc:
            self.sequence_timer.stop();self.timer.stop();self.sequence_executor.stop("error");self.sequence_execute.setEnabled(True);self.sequence_stop.setEnabled(False);self.stop.setEnabled(False);self.start.setEnabled(True);self.manager.setEnabled(True);self.instance.setEnabled(True);self.recipe.setEnabled(True);self._update_sequence_highlight(None);self.sequence_status.setText(f"Sequence ERROR: {exc}");self.result["STATUS"].setText("ERROR");logger.exception("Sequence execution failed");QMessageBox.critical(self,"Sequence Error",str(exc))

    def _stop_sequences(self):
        self.sequence_timer.stop();self.timer.stop();self.sequence_executor.stop("operator_stop");self.sequence_execute.setEnabled(True);self.sequence_stop.setEnabled(False);self.stop.setEnabled(False);self.start.setEnabled(True);self.manager.setEnabled(True);self.instance.setEnabled(True);self.recipe.setEnabled(True);self._update_sequence_highlight(None);self.sequence_status.setText("停止");self.run_state.setText("STOPPED")

def build_context():
    serial_controller=SerialController(serial_port="/dev/ttyACM0",baudrate=57600)
    builder=ApplicationBuilder(serial_controller=serial_controller)
    breakin_controller=builder.build_breakin_controller()
    battery_serial_controller=BatterySerial(port="/dev/ttyUSB0",baudrate=57600)
    return {"serial_controller":serial_controller,"breakin_controller":breakin_controller,"battery_serial_controller":battery_serial_controller}

def main():
    app=QApplication(sys.argv);context=build_context();window=MainWindow(context);window.show();return app.exec_()

if __name__=="__main__":sys.exit(main())
