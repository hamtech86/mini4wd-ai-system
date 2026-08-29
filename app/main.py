"""MINI4WD AI SYSTEM / MOTOR_BREAKIN_V3 application entry point."""
import sys
from pathlib import Path
PROJECT_ROOT=Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path: sys.path.insert(0,str(PROJECT_ROOT))
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication,QMessageBox,QGroupBox,QGridLayout,QLabel,QPushButton,QScrollArea,QHBoxLayout,QVBoxLayout,QWidget,QTabWidget
from loguru import logger
from config import APP_NAME,APP_VERSION,LOG_DIR
from ui.main_window import MainWindow as BaseMainWindow
from ui.motor_analysis_display import MotorVoltageResultWidget
from analysis.three_volt_window import extract_3v_window,motor_voltage
from communication.serial_controller import SerialController
from battery_system.serial import BatterySerial
from app.application_builder import ApplicationBuilder
from ui.resume_controls import install_resume_controls,bind_resume_api
from ui.battery_tab_ui import BatteryTab

class MainWindow(BaseMainWindow):
    """Main UI with separate Motor Break-in and Battery tabs."""
    def __init__(self,context=None):
        super().__init__(context)
        bind_resume_api(type(self)); install_resume_controls(self)
        context=context if isinstance(context,dict) else {}
        # BaseMainWindow receives the BreakinController, but the operator
        # connection controls must use the exact SerialController instance
        # created by ApplicationRuntimeBuilder.
        self.serial_controller=context.get("serial_controller")
        self.battery_serial_controller=context.get("battery_serial_controller")
        self._extract_motor_page(); self._build_estimated_result_panel(); self._build_voltage_result_panel(); self._build_integrated_ui()
    def _extract_motor_page(self):
        central=self.centralWidget()
        if central is None:return
        scroll=central.findChild(QScrollArea); self.motor_page=central; self.motor_content=scroll.widget() if scroll is not None else None
        if self.motor_content is None:return
        layout=self.motor_content.layout()
        if layout is None:return
        for i in range(layout.count()-1,-1,-1):
            w=layout.itemAt(i).widget() if layout.itemAt(i) else None
            if w is not None and (w.objectName()=="legacy_device_connection" or w.objectName()=="battery_database_button"):
                layout.removeWidget(w); w.setParent(None); w.deleteLater()
    def _build_integrated_ui(self):
        old_central=self.takeCentralWidget() or self.motor_page
        root=QWidget(); root_layout=QVBoxLayout(root); root_layout.setContentsMargins(5,5,5,5)
        device_box=QGroupBox("DEVICE CONNECTION"); row=QGridLayout(device_box)
        self.motor_serial_status=QLabel("MOTOR: DISCONNECTED  /dev/ttyACM0"); self.motor_connect=QPushButton("MOTOR CONNECT"); self.motor_disconnect=QPushButton("MOTOR DISCONNECT"); self.motor_disconnect.setEnabled(False)
        self.battery_serial_status=QLabel("BATTERY: DISCONNECTED  /dev/ttyUSB0"); self.battery_connect=QPushButton("BATTERY CONNECT"); self.battery_disconnect=QPushButton("BATTERY DISCONNECT"); self.battery_disconnect.setEnabled(False)
        self.motor_connect.clicked.connect(self.connect_motor_serial); self.motor_disconnect.clicked.connect(self.disconnect_motor_serial); self.battery_connect.clicked.connect(self.connect_battery_serial); self.battery_disconnect.clicked.connect(self.disconnect_battery_serial)
        row.addWidget(self.motor_serial_status,0,0); row.addWidget(self.motor_connect,0,1); row.addWidget(self.motor_disconnect,0,2); row.addWidget(self.battery_serial_status,1,0); row.addWidget(self.battery_connect,1,1); row.addWidget(self.battery_disconnect,1,2); root_layout.addWidget(device_box)
        tabs=QTabWidget(); tabs.addTab(old_central,"MOTOR BREAK-IN")
        self.battery_tab=BatteryTab(self.db_path,transport=self.battery_serial_controller,parent=self); tabs.addTab(self.battery_tab,"BATTERY"); root_layout.addWidget(tabs,1); self.setCentralWidget(root)
    def _motor_controller(self):
        return self.serial_controller
    def connect_motor_serial(self):
        c=self._motor_controller()
        if c is None: QMessageBox.warning(self,"Motor Connection","Serial controller is not available."); return
        if c.connected:return
        if c.connect(): self.motor_serial_status.setText("MOTOR: CONNECTED  /dev/ttyACM0 @ 57600"); self.motor_connect.setEnabled(False); self.motor_disconnect.setEnabled(True)
        else: self.motor_serial_status.setText(f"MOTOR: CONNECTION FAILED  /dev/ttyACM0 ({getattr(c,'last_error','serial connection failed')})")
    def disconnect_motor_serial(self):
        c=self._motor_controller()
        if c is not None:
            try:
                if c.connected:c.stop_breakin()
            except Exception:logger.exception("Failed to stop motor before disconnect")
            try:c.disconnect()
            except Exception:logger.exception("Failed to disconnect motor serial")
        self.motor_serial_status.setText("MOTOR: DISCONNECTED  /dev/ttyACM0"); self.motor_connect.setEnabled(True); self.motor_disconnect.setEnabled(False)
    def connect_battery_serial(self):
        c=self.battery_serial_controller
        if c is None: QMessageBox.warning(self,"Battery Connection","Battery serial controller is not available."); return
        if c.connected:return
        if not c.connect(): self.battery_serial_status.setText(f"BATTERY: CONNECTION FAILED  /dev/ttyUSB0 ({c.last_error})"); return
        self.battery_serial_status.setText("BATTERY: CONNECTED  /dev/ttyUSB0 @ 57600"); self.battery_connect.setEnabled(False); self.battery_disconnect.setEnabled(True); self.battery_tab.set_connected(True)
    def disconnect_battery_serial(self):
        c=self.battery_serial_controller
        if c is not None:
            try:c.disconnect()
            except Exception:logger.exception("Failed to disconnect battery serial")
        self.battery_serial_status.setText("BATTERY: DISCONNECTED  /dev/ttyUSB0"); self.battery_connect.setEnabled(True); self.battery_disconnect.setEnabled(False); self.battery_tab.set_connected(False)
    def _build_estimated_result_panel(self):
        content=self.motor_content; layout=content.layout() if content is not None else None
        if layout is None:return
        self.estimated_result={k:QLabel("--") for k in ("UNLOADED_RPM","TORQUE","BRUSH_SCORE","WEIGHT")}; box=QGroupBox("ESTIMATED PERFORMANCE / 推定値"); grid=QGridLayout(box)
        labels=(("無負荷回転数（推定）","UNLOADED_RPM"),("トルク（推定）","TORQUE"),("ブラシピーク（解析）","BRUSH_SCORE"),("対応車重（暫定推定）","WEIGHT"))
        for i,(title,key) in enumerate(labels):
            card=QGroupBox(title); cl=QGridLayout(card); v=self.estimated_result[key]; v.setAlignment(Qt.AlignCenter); v.setStyleSheet("font-size:16px;font-weight:bold;"); cl.addWidget(v,0,0); grid.addWidget(card,i//2,i%2)
        layout.addWidget(box)
    def _build_voltage_result_panel(self):
        layout=self.motor_content.layout() if self.motor_content is not None else None
        if layout is None:return
        self.voltage_result_widget=MotorVoltageResultWidget(self); layout.addWidget(self.voltage_result_widget)
    @staticmethod
    def _as_float(value,default=0.0):
        try:return float(value)
        except (TypeError,ValueError):return default
    def _analysis_series(self):
        data=getattr(self,"last_result_data",None)
        if isinstance(data,list):return [x for x in data if hasattr(x,"performance")]
        return [data] if hasattr(data,"performance") else []
    def _estimated_values(self):
        analyses=self._analysis_series()
        if not analyses:return "データ不足","データ不足","データ不足","データ不足"
        rpm=[self._as_float(getattr(a.performance.estimated_no_load_rpm,"value",None)) for a in analyses]; torque=[self._as_float(getattr(a.performance.estimated_torque,"value",None)) for a in analyses]; weight=[self._as_float(getattr(a.performance.estimated_supported_weight,"value",None)) for a in analyses]
        rpm=[x for x in rpm if x>0]; torque=[x for x in torque if x>0]; weight=[x for x in weight if x>0]
        r=sum(rpm)/len(rpm) if rpm else 0; t=sum(torque)/len(torque) if torque else 0; w=sum(weight)/len(weight) if weight else 0
        scores=[]; peaks=[]; conditions=[]
        for a in analyses:
            b=getattr(a,"brush",None)
            if b is None:continue
            scores.append(self._as_float(getattr(getattr(b,"peak_score",None),"value",None))); p=self._as_float(getattr(getattr(b,"peak_position",None),"value",None));
            if p>0:peaks.append(p)
            conditions.append(str(getattr(b,"brush_condition","UNKNOWN") or "UNKNOWN"))
        if scores:
            score=sum(scores)/len(scores); peak=max(peaks) if peaks else 0; cond=max(set(conditions),key=conditions.count) if conditions else "UNKNOWN"; brush=f"{score:+.1f} / 10　{cond}"+(f"　peak {peak:.3f} A" if peak>0 else "")
        else:brush="データ不足"
        return (f"{r:,.0f} rpm" if r>0 else "データ不足",f"{t:.2f} g·cm" if t>0 else "データ不足",brush,f"{w:,.0f} g（暫定）" if w>0 else "データ不足")
    def _refresh_estimated_values(self):
        if not hasattr(self,"estimated_result"):return
        for key,value in zip(("UNLOADED_RPM","TORQUE","BRUSH_SCORE","WEIGHT"),self._estimated_values()):self.estimated_result[key].setText(value)
    def _measurement_series(self):
        c=self.breakin_controller; return list(getattr(c,"measurements",[]) or []) if c else []
    @staticmethod
    def _measurement_value(m,*names):
        if isinstance(m,dict):
            for n in names:
                if m.get(n) is not None:return m[n]
        else:
            for n in names:
                v=getattr(m,n,None)
                if v is not None:return v
        return None
    def _refresh_voltage_result(self):
        if not hasattr(self,"voltage_result_widget"):return
        window=extract_3v_window(self._measurement_series()); sample=window.max_voltage_sample
        if sample is None:self.voltage_result_widget.set_values(reached_3v=False); return
        voltage=motor_voltage(sample); rpm=self._measurement_value(sample,"rpm","RPM","revolutions_per_minute"); current=self._measurement_value(sample,"current_avg","average_current","current"); power=self._measurement_value(sample,"power")
        if voltage<=0:self.voltage_result_widget.set_values(reached_3v=window.reached_3v); return
        ratio=2.8/3.0; pf=lambda x:x*ratio if x is not None else None
        self.voltage_result_widget.set_values(measured_voltage=voltage,measured_rpm=rpm,measured_current=current,measured_power=power,projected_rpm=pf(self._as_float(rpm,None)) if rpm is not None else None,projected_current=pf(self._as_float(current,None)) if current is not None else None,projected_power=self._as_float(power,None)*ratio*ratio if power is not None else None,reached_3v=window.reached_3v)
    def complete(self,data,benchmark): super().complete(data,benchmark); self._refresh_estimated_values(); self._refresh_voltage_result()
    def failed(self,message):
        super().failed(message)
        if hasattr(self,"estimated_result"):
            for v in self.estimated_result.values():v.setText("NOT AVAILABLE")
        if hasattr(self,"voltage_result_widget"):self.voltage_result_widget.set_values(reached_3v=False)

class ApplicationRuntimeBuilder:
    MOTOR_PORT="/dev/ttyACM0"; BATTERY_PORT="/dev/ttyUSB0"; SERIAL_BAUDRATE=57600
    def __init__(self):self.serial_controller=None; self.battery_serial_controller=None
    def build_context(self):
        self.serial_controller=SerialController(serial_port=self.MOTOR_PORT,baudrate=self.SERIAL_BAUDRATE); self.battery_serial_controller=BatterySerial(port=self.BATTERY_PORT,baudrate=self.SERIAL_BAUDRATE); builder=ApplicationBuilder(serial_controller=self.serial_controller)
        return {"serial_controller":self.serial_controller,"breakin_controller":builder.build_breakin_controller(),"serial_connected":False,"battery_serial_controller":self.battery_serial_controller}
    def close(self):
        for c in (self.serial_controller,self.battery_serial_controller):
            if c is None:continue
            try:
                if c.connected:c.disconnect()
            except Exception:logger.exception("Failed to disconnect serial device during shutdown")

def setup_logger():
    logger.remove(); logger.add(sys.stdout,level="INFO",colorize=True); logger.add(LOG_DIR/"system.log",rotation="10 MB",retention=10,encoding="utf-8",level="DEBUG")
def main():
    setup_logger(); app=QApplication(sys.argv); app.setApplicationName(APP_NAME); app.setApplicationVersion(APP_VERSION); runtime=ApplicationRuntimeBuilder()
    try:
        context=runtime.build_context(); window=MainWindow(context); window.show(); app.aboutToQuit.connect(runtime.close); return app.exec()
    except Exception:
        logger.exception("Fatal Error"); runtime.close(); QMessageBox.critical(None,"Fatal Error","致命的なエラーが発生しました。\nsystem.log を確認してください。"); return 1
if __name__=="__main__":sys.exit(main())