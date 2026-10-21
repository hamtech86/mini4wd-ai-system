"""MINI4WD AI SYSTEM / MOTOR_BREAKIN_V3 application entry point."""
import sys
import sqlite3
from pathlib import Path
from datetime import datetime
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.path_resolver import configure_shared_database_path, connect_database
# Resolve once before UI modules construct their database-backed windows.
# Explicit MINI4WD_DB_PATH remains authoritative; the default is the main
# checkout's database/mini4wd.db shared by linked Git worktrees.
configure_shared_database_path(PROJECT_ROOT)

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QApplication, QMessageBox, QGroupBox, QGridLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget, QTabWidget, QHBoxLayout, QCheckBox, QProgressBar, QPlainTextEdit
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
from controllers.session_controller import SessionController
from controllers.motor_benchmark import STANDARD_3V30S, FULL_PACKAGE
from controllers.current_display import format_driver_input_current, format_input_voltage, format_motor_voltage
from controllers.ui_benchmark_presets import BENCHMARK_PRESETS as UI_BENCHMARK_PRESETS


class MainWindow(BaseMainWindow):
    def __init__(self, context=None):
        super().__init__(context)
        self._stop_latched = False
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
        root_layout.addWidget(device_box)
        # Fixed emergency stop outside the scrollable MOTOR tab.
        self.emergency_stop_fixed = QPushButton("EMERGENCY STOP")
        self.emergency_stop_fixed.setMinimumHeight(44)
        # Keep the physical-stop request available even while idle; it must
        # never be disabled by recipe selection, scrolling, or run-state changes.
        self.emergency_stop_fixed.setEnabled(True)
        self.emergency_stop_fixed.clicked.connect(self.stop_run)
        root_layout.addWidget(self.emergency_stop_fixed)
        tabs=QTabWidget(); tabs.addTab(old_central,"MOTOR BREAK-IN"); self.battery_tab=BatteryTab(self.db_path,transport=self.battery_serial_controller,parent=self); tabs.addTab(self.battery_tab,"BATTERY"); root_layout.addWidget(tabs,1); self._build_ui_log_panel(root_layout); self.setCentralWidget(root)

    BENCHMARK_PRESETS = UI_BENCHMARK_PRESETS

    def load_recipes(self):
        # Only the four canonical benchmark combinations are exposed.
        self.recipe.clear()
        for label in self.BENCHMARK_PRESETS:
            self.recipe.addItem(label, label)

    def recipe_changed(self, index):
        # Base MainWindow populates the combo during super().__init__, before
        # this subclass builds the benchmark panel.
        if not hasattr(self, "sequence_layout"):
            return
        name = self.recipe.itemData(index) if hasattr(self, "recipe") else None
        if name not in self.BENCHMARK_PRESETS:
            self._clear_sequence_panel("Unsupported recipe blocked; select one of STD-T, Full-T, STD-I, Full-I.")
            self.start.setEnabled(False)
            self.sequence_execute.setEnabled(False)
            return
        benchmark_type, mode = self.BENCHMARK_PRESETS[name]
        self._load_benchmark_sequence(benchmark_type, mode, name)
        self.start.setEnabled(True)
        self.sequence_execute.setEnabled(True)

    def _build_ui_log_panel(self, parent_layout):
        box=QGroupBox("LOG / ERROR LOG"); layout=QVBoxLayout(box)
        self.ui_log=QPlainTextEdit(); self.ui_log.setReadOnly(True); self.ui_log.setMaximumBlockCount(500); self.ui_log.setPlaceholderText("Controller / UI / Sequence events will appear here."); layout.addWidget(self.ui_log)
        self.error_code_label=QLabel("Error Code: --"); self.error_message_label=QLabel("Error Message: --"); self.error_message_label.setWordWrap(True); layout.addWidget(self.error_code_label); layout.addWidget(self.error_message_label)
        actions=QHBoxLayout(); self.copy_error_button=QPushButton("COPY ERROR DETAILS"); self.copy_error_button.setEnabled(False); self.copy_error_button.clicked.connect(self.copy_error_details); actions.addWidget(self.copy_error_button)
        clear=QPushButton("CLEAR LOG"); clear.clicked.connect(self.ui_log.clear); actions.addWidget(clear); actions.addStretch(); layout.addLayout(actions); parent_layout.addWidget(box)
        self._ui_error_code=None; self._ui_error_message=None; self._log_event("UI ready; hardware identity has not been verified."); self._log_event("Driver input current uses ACS712 #1/A0 current1 from the documented wiring; this is not motor winding current.")

    def _log_event(self, message):
        if hasattr(self,"ui_log"):
            stamp=datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z"); self.ui_log.appendPlainText(f"[{stamp}] {message}")

    def _set_ui_error(self, code, message):
        self._ui_error_code=str(code) if code else None; self._ui_error_message=str(message) if message else None
        self.error_code_label.setText(f"Error Code: {self._ui_error_code or '--'}"); self.error_message_label.setText(f"Error Message: {self._ui_error_message or '--'}")
        self.copy_error_button.setEnabled(bool(self._ui_error_code or self._ui_error_message))
        if self._ui_error_message: self._log_event(f"ERROR {self._ui_error_code or '--'}: {self._ui_error_message}")

    def copy_error_details(self):
        if not (self._ui_error_code or self._ui_error_message): return
        parts=[]
        if self._ui_error_code: parts.append(f"Error Code: {self._ui_error_code}")
        if self._ui_error_message: parts.append(f"Error Message: {self._ui_error_message}")
        QApplication.clipboard().setText("\n".join(parts)); self.copy_error_button.setText("COPIED ERROR DETAILS")

    def _identity_verified(self, controller=None):
        controller=controller or self._motor_controller()
        return bool(controller is not None and getattr(controller,"identity_verified",False) is True)

    def _require_verified_motor(self, operation):
        if self._identity_verified(): return True
        message=f"{operation} blocked: serial-port connection is not device identification. No valid INFO identity has been verified; no drive command was issued."
        self._set_ui_error("MOTOR_IDENTITY_UNVERIFIED",message); self.run_state.setText("BLOCKED / INFO NOT VERIFIED")
        if hasattr(self,"result") and "STATUS" in self.result: self.result["STATUS"].setText("BLOCKED / INFO NOT VERIFIED")
        self._log_event(message); return False

    def _motor_controller(self):
        controller=getattr(self,"serial_controller",None)
        if controller is not None:return controller
        controller=getattr(getattr(self,"breakin_controller",None),"serial",None)
        if controller is not None:return controller
        return getattr(getattr(self,"breakin_controller",None),"serial_controller",None)

    def open_manager(self):
        """Open the Motor Instance Manager with the Local Raw Log manager attached."""
        try:
            from motor_system.python.ui.motor_manager_ui import MotorManagerUI

            instance_id = self.instance.currentData() if hasattr(self, "instance") else None
            self.manager_window = MotorManagerUI()

            if instance_id is not None:
                self.manager_window.load_instance_into_form(instance_id)
                self.manager_window.show_instance_detail(instance_id)

            self.manager_window.setAttribute(Qt.WA_DeleteOnClose, True)
            self.manager_window.destroyed.connect(self.load_instances)
            self.manager_window.show()
            self.manager_window.raise_()
            self.manager_window.activateWindow()
        except Exception as exc:
            logger.exception("Failed to open Motor Instance Manager")
            QMessageBox.critical(
                self,
                "Instance Manager",
                f"Motor Instance Managerを起動できません。\n{type(exc).__name__}: {exc}",
            )

    def connect_motor_serial(self):
        controller=self._motor_controller()
        if controller is None:
            message="Motor serial controller is not available."; self._set_ui_error("MOTOR_CONTROLLER_UNAVAILABLE",message); QMessageBox.warning(self,"Motor Connection",message); return
        if controller.connected: self.motor_serial_status.setText("MOTOR: PORT CONNECTED / INFO NOT VERIFIED"); return
        if controller.connect():
            self.motor_connect.setEnabled(False); self.motor_disconnect.setEnabled(True)
            if self._identity_verified(controller):
                info = getattr(controller, "device_info", {}) or {}
                self.motor_serial_status.setText("MOTOR: IDENTITY VERIFIED / " + str(info.get("MODEL")) + " / FW " + str(info.get("FW")) + " / " + str(info.get("ID")))
                self._log_event("Motor INFO identity verified: " + str(info))
            else:
                self.motor_serial_status.setText("MOTOR: PORT CONNECTED / INFO NOT VERIFIED — DRIVE BLOCKED")
                self._set_ui_error("MOTOR_IDENTITY_UNVERIFIED",getattr(controller,"identity_error","INFO identity was not verified."))
        else:
            self.motor_serial_status.setText("MOTOR: CONNECTION FAILED  /dev/ttyACM0"); self._set_ui_error("MOTOR_SERIAL_CONNECT_FAILED","SerialController.connect() returned failure; device identity was not verified.")

    def disconnect_motor_serial(self):
        controller=self._motor_controller()
        if controller is not None:
            try:
                if controller.connected:controller.stop_breakin()
            except Exception:logger.exception("Failed to stop motor before disconnect")
            try:controller.disconnect()
            except Exception:logger.exception("Failed to disconnect motor serial")
        if hasattr(self,"sequence_executor"):self.sequence_executor.stop("motor_disconnected")
        self.motor_serial_status.setText("MOTOR: DISCONNECTED  /dev/ttyACM0"); self.motor_connect.setEnabled(True); self.motor_disconnect.setEnabled(False); self._log_event("Motor serial disconnected. Any STOP command sent before disconnect is not physical-stop confirmation.")

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
            conn=connect_database(self.db_path, readonly=True)
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
        box=QGroupBox("BENCHMARK PLAN");root=QVBoxLayout(box);self.sequence_all=QPushButton("全選択");self.sequence_none=QPushButton("全解除");self.sequence_execute=QPushButton("選択Sequenceを実行");self.sequence_stop=QPushButton("Sequence停止")
        # Retire generic sequence controls; this panel is display-only.
        for control in (self.sequence_all, self.sequence_none, self.sequence_execute, self.sequence_stop):
            control.hide()
        self.sequence_stop.setEnabled(False)
        self.sequence_progress=QProgressBar();self.sequence_progress.setRange(0,100);self.sequence_progress.setValue(0);self.sequence_progress.setFormat("Sequence Progress: %p%")
        root.addWidget(self.sequence_progress);self.sequence_status=QLabel("未実行");root.addWidget(self.sequence_status);scroll=QScrollArea();scroll.setWidgetResizable(True);body=QWidget();self.sequence_layout=QVBoxLayout(body);scroll.setWidget(body);root.addWidget(scroll,1);self.sequence_checks=[];layout=self.motor_content.layout() if self.motor_content is not None else None
        if layout is not None:layout.insertWidget(1,box)
        self.recipe.currentIndexChanged.connect(self._recipe_selection_changed)
        self._recipe_selection_changed(self.recipe.currentIndex())

    def _current_recipe_name(self):
        return self.recipe.currentData() if hasattr(self,"recipe") else None

    def _recipe_selection_changed(self,index):
        # Fail closed: legacy YAML recipe execution is retired.
        name=self.recipe.itemData(index) if hasattr(self,"recipe") else None
        if name not in self.BENCHMARK_PRESETS:
            self._clear_sequence_panel("Unsupported recipe blocked; only four benchmark presets are allowed.")
            self.sequence_execute.setEnabled(False)
            self.start.setEnabled(False)
            return
        benchmark_type, mode = self.BENCHMARK_PRESETS[name]
        self._load_benchmark_sequence(benchmark_type, mode, name)
        self.sequence_execute.setEnabled(True)
        self.start.setEnabled(True)

    def _clear_sequence_panel(self,status):
        while self.sequence_layout.count():
            item=self.sequence_layout.takeAt(0);widget=item.widget()
            if widget is not None:widget.deleteLater()
        self.sequence_checks=[];self.sequence_progress.setValue(0);self.sequence_status.setText(status)

    def _load_benchmark_sequence(self, benchmark_type, mode="TERMINAL", preset_label=None):
        label=preset_label or ("STD-T" if benchmark_type==STANDARD_3V30S else "Full-T")
        self._clear_sequence_panel(f"Motor Benchmark: {label} / {benchmark_type} / {mode}")
        detail=("01 | STANDARD_3V30S | PREPARE 2 s → 3.00 V target 30 s" if benchmark_type==STANDARD_3V30S else "01 | FULL_PACKAGE | PREPARE 2 s → BASELINE 30 s → +5% 30 s → RETURN 10 s → -5% 30 s → RETURN 10 s")
        check=QCheckBox(f"{label} | Benchmark Type={('STANDARD' if benchmark_type==STANDARD_3V30S else 'FULL_PACKAGE')} | Voltage Control Mode={mode} | {detail}")
        check.setChecked(True); check.setProperty("benchmark_type",benchmark_type); check.setProperty("voltage_control_mode",mode); check.setProperty("preset_label",label)
        self.sequence_layout.addWidget(check); self.sequence_checks=[(label,check)]; self.sequence_layout.addStretch()
        status=f"Motor Benchmark: {label} / {benchmark_type} / {mode}"
        self.sequence_status.setText(status)
        self.recipe_detail.setText(f"Benchmark Type: {('STANDARD' if benchmark_type==STANDARD_3V30S else 'FULL_PACKAGE')} / Voltage Control Mode: {mode}")
        self.phase_detail.setText(detail)
        self.benchmark_detail.setText("3.00 V / 30 s; control mode shown explicitly")
        self._log_event(f"Recipe selected: {label} (Benchmark Type={('STANDARD' if benchmark_type==STANDARD_3V30S else 'FULL_PACKAGE')}, Voltage Control Mode={mode}).")

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
        elapsed=getattr(result,"elapsed_sec",None) if result is not None else None
        if hasattr(self,"progress"):
            values={"STEP":f"{min(completed+1,total)} / {total}","PHASE":getattr(current,"sequence_id","--"),"DIR":getattr(current,"direction","--"),"PWM":getattr(current,"pwm","--"),"INPUT VOLTAGE":format_input_voltage(m,getattr(current,"direction",None)),"MOTOR VOLTAGE":format_motor_voltage(m),"DRIVER INPUT CURRENT":format_driver_input_current(m),"ELAPSED":f"{elapsed:.1f} s" if elapsed is not None else "--","REMAIN":f"{remaining:.1f} s" if remaining is not None else "--"}
            for key,value in values.items():
                if key in self.progress:self.progress[key].setText(str(value))
        if hasattr(self,"live"):
            # Keep supplemental live status, RPM and temperature separate from
            # the single canonical seven-field execution telemetry display.
            values={"RPM":self._latest_rpm() if hasattr(self,"_latest_rpm") else "--","STATE":"RUNNING","TEMP":f"{float(getattr(m,'motor_temperature')):.1f} C" if m is not None and getattr(m,"motor_temperature",None) is not None else "--","Arduino":("IDENTITY VERIFIED" if self._identity_verified() else "PORT CONNECTED / INFO UNVERIFIED")}
            for key,value in values.items():
                if key in self.live:self.live[key].setText(str(value))
        self.sequence_status.setText(f"実行中: {current.sequence_id}  {progress}%  残り {remaining:.1f}s" if remaining is not None else f"実行中: {current.sequence_id}  {progress}%  条件待ち")

    def _execute_selected_sequences(self):
        # Compatibility slot for START. Generic recipe/sequence execution is retired.
        name = self._current_recipe_name()
        preset = self.BENCHMARK_PRESETS.get(name)
        if preset is None:
            self._set_ui_error("UNSUPPORTED_RECIPE", "Only STD-T, Full-T, STD-I, and Full-I are allowed.")
            self.sequence_status.setText("BLOCKED / unsupported recipe")
            return
        benchmark_type, mode = preset
        if not self._require_verified_motor(name):
            self.sequence_status.setText(f"{name}: BLOCKED / INFO NOT VERIFIED")
            return
        self._start_benchmark(benchmark_type, mode)

    def _start_benchmark(self, benchmark_type=STANDARD_3V30S, voltage_control_mode="TERMINAL"):
        if self._stop_latched:
            self._set_ui_error("STOP_LATCHED", "Restart blocked after an emergency-stop request; physical stop remains unconfirmed.")
            return
        if not self._require_verified_motor("Motor Benchmark"): return
        if not self.breakin_controller:
            QMessageBox.warning(self,"Controller","BreakinController is not available.");return
        controller=self._motor_controller()
        if controller is None or not getattr(controller,"connected",False):QMessageBox.warning(self,"Benchmark","先にMOTOR CONNECTを実行してください。");return
        self.breakin_controller.selected_benchmark_type=benchmark_type
        self.breakin_controller.selected_benchmark_voltage_mode=voltage_control_mode
        self.database_updated=False;self.last_result_data=None;self.last_result_benchmark=True;self.database_status.setText("DATABASE: NOT UPDATED");self.update_db.setEnabled(False);self.copy.setEnabled(False);self.start.setEnabled(False);self.manager.setEnabled(False);self.instance.setEnabled(False);self.recipe.setEnabled(False);self.stop.setEnabled(True);self.emergency_stop_fixed.setEnabled(True);self.result["STATUS"].setText("RUNNING");self.run_state.setText("STARTING...")
        self.breakin_worker=BreakinWorker(self.breakin_controller,None,True)
        self.breakin_worker.completed.connect(lambda data:self.complete(data,True));self.breakin_worker.failed.connect(self.failed);self.breakin_worker.finished.connect(self.finished);self.timer.start();self.breakin_worker.start()

    def start_run(self):
        self._execute_selected_sequences()

    def complete(self,data,benchmark):
        super().complete(data,benchmark)
        self._log_event("Measurement run completed. This status does not certify physical stop unless separately observed.")
        self._update_estimated_result()

    def failed(self,message):
        self._set_ui_error(None, message)
        self._log_event("Worker reported failure; see Error Message for the actual reported text.")
        super().failed(message)

    def stop_run(self):
        self._stop_latched = True
        stop_errors = []
        controller = getattr(self, "breakin_controller", None)
        if controller is None:
            controller = self._motor_controller()
        try:
            if controller is None:
                stop_errors.append("No motor controller available; serial STOP could not be attempted.")
            elif hasattr(controller, "emergency_stop"):
                controller.emergency_stop()
            elif hasattr(controller, "stop_breakin"):
                controller.stop_breakin()
            else:
                stop_errors.append("Controller has no emergency_stop/stop_breakin method.")
        except Exception as exc:
            stop_errors.append(f"Controller stop: {type(exc).__name__}: {exc}")
            # If the BreakinController path failed before reaching serial,
            # make an independent best-effort attempt through SerialController.
            serial_controller = self._motor_controller()
            if serial_controller is not None and serial_controller is not controller:
                try:
                    if hasattr(serial_controller, "emergency_stop"):
                        serial_controller.emergency_stop()
                    elif hasattr(serial_controller, "stop_breakin"):
                        serial_controller.stop_breakin()
                    else:
                        stop_errors.append("Serial controller has no supported stop method.")
                except Exception as fallback_exc:
                    stop_errors.append(f"Direct serial stop: {type(fallback_exc).__name__}: {fallback_exc}")
        try:
            if hasattr(self, "sequence_executor"):
                self.sequence_executor.stop("emergency_stop")
        except Exception as exc:
            stop_errors.append(f"Sequence cancellation: {type(exc).__name__}: {exc}")
        self.sequence_timer.stop()
        self.timer.stop()
        self.sequence_execute.setEnabled(False)
        self.sequence_stop.setEnabled(False)
        self.stop.setEnabled(False)
        self.emergency_stop_fixed.setEnabled(True)
        self.start.setEnabled(False)
        self.manager.setEnabled(False)
        self.instance.setEnabled(False)
        self.recipe.setEnabled(False)
        self.run_state.setText("STOP REQUESTED / PHYSICAL STOP UNCONFIRMED")
        self.result["STATUS"].setText("STOP REQUESTED / UNCONFIRMED")
        self.sequence_status.setText("停止要求を送信しました。物理停止は未確認です。")
        details = "; ".join(stop_errors) if stop_errors else "software stop path attempted; physical stop unconfirmed"
        self._log_event(f"Emergency STOP requested; {details}. Restart remains latched.")
        if stop_errors:
            self._set_ui_error("EMERGENCY_STOP_PATH_ERROR", details)
        self._update_sequence_highlight(None)

    def finished(self):
        # Base MainWindow.finished() unconditionally re-enables START. Preserve
        # the emergency-stop latch across asynchronous worker completion.
        super().finished()
        if self._stop_latched:
            self.start.setEnabled(False)
            self.manager.setEnabled(False)
            self.instance.setEnabled(False)
            self.recipe.setEnabled(False)
            self.emergency_stop_fixed.setEnabled(True)
            self.run_state.setText("STOP REQUESTED / PHYSICAL STOP UNCONFIRMED")
            self.result["STATUS"].setText("STOP REQUESTED / UNCONFIRMED")

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
            self.sequence_timer.stop();self.timer.stop();self.sequence_executor.stop("error");self.sequence_execute.setEnabled(True);self.sequence_stop.setEnabled(False);self.stop.setEnabled(False);self.start.setEnabled(True);self.manager.setEnabled(True);self.instance.setEnabled(True);self.recipe.setEnabled(True);self._update_sequence_highlight(None);self.sequence_status.setText(f"Sequence ERROR: {exc}");self.result["STATUS"].setText("ERROR");self._set_ui_error(type(exc).__name__,str(exc));logger.exception("Sequence execution failed");QMessageBox.critical(self,"Sequence Error",str(exc))

    def _stop_sequences(self):
        self.sequence_timer.stop();self.timer.stop();self.sequence_executor.stop("operator_stop");self.sequence_execute.setEnabled(True);self.sequence_stop.setEnabled(False);self.stop.setEnabled(False);self.start.setEnabled(True);self.manager.setEnabled(True);self.instance.setEnabled(True);self.recipe.setEnabled(True);self._update_sequence_highlight(None);self.sequence_status.setText("停止要求を送信しました。物理停止は未確認です。");self.run_state.setText("STOP REQUESTED / PHYSICAL STOP UNCONFIRMED");self.result["STATUS"].setText("STOP REQUESTED / UNCONFIRMED");self._log_event("Sequence STOP requested; physical motor stop is unconfirmed.")

def build_context():
    serial_controller=SerialController(serial_port="/dev/ttyACM0",baudrate=57600)
    session_controller=SessionController()
    builder=ApplicationBuilder(serial_controller=serial_controller,session_manager=session_controller)
    breakin_controller=builder.build_breakin_controller()
    battery_serial_controller=BatterySerial(port="/dev/ttyUSB0",baudrate=57600)
    return {"serial_controller":serial_controller,"breakin_controller":breakin_controller,"battery_serial_controller":battery_serial_controller}

def main():
    app=QApplication(sys.argv);context=build_context();window=MainWindow(context);window.show();return app.exec_()

if __name__=="__main__":sys.exit(main())
