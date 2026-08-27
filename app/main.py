"""MINI4WD AI SYSTEM / MOTOR_BREAKIN_V3 application entry point."""
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path: sys.path.insert(0, str(PROJECT_ROOT))
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMessageBox, QGroupBox, QGridLayout, QLabel, QPushButton, QScrollArea, QHBoxLayout, QVBoxLayout, QWidget
from loguru import logger
from config import APP_NAME, APP_VERSION, LOG_DIR
from ui.main_window import MainWindow as BaseMainWindow
from communication.serial_controller import SerialController
from app.application_builder import ApplicationBuilder
from ui.resume_controls import install_resume_controls, bind_resume_api
from ui.battery_database_ui import BatteryDatabaseDialog

class MainWindow(BaseMainWindow):
    """Main UI with operator-facing motor results and Battery DB registration."""
    def __init__(self, context=None):
        super().__init__(context); bind_resume_api(type(self)); install_resume_controls(self); self._build_top_controls(); self._build_estimated_result_panel(); self._build_battery_db_button()
    def _content_layout(self):
        central=self.centralWidget(); scroll=central.findChild(QScrollArea) if central is not None else None; content=scroll.widget() if scroll is not None else None; return content.layout() if content is not None else None, content
    def _build_top_controls(self):
        central=self.centralWidget()
        if central is None: return
        root=central.layout()
        if root is None: return
        box=QGroupBox("DEVICE CONNECTION")
        row=QHBoxLayout(box)
        self.serial_status=QLabel("MOTOR: DISCONNECTED  /dev/ttyACM0")
        self.serial_connect_button=QPushButton("MOTOR CONNECT")
        self.serial_disconnect_button=QPushButton("MOTOR DISCONNECT")
        self.serial_disconnect_button.setEnabled(False)
        self.serial_connect_button.clicked.connect(self.connect_motor_serial)
        self.serial_disconnect_button.clicked.connect(self.disconnect_motor_serial)
        row.addWidget(self.serial_status); row.addWidget(self.serial_connect_button); row.addWidget(self.serial_disconnect_button)
        root.insertWidget(0,box)
    def connect_motor_serial(self):
        controller=getattr(self,"serial_controller",None)
        if controller is None: controller=getattr(getattr(self,"breakin_controller",None),"serial_controller",None)
        if controller is None:
            QMessageBox.warning(self,"Motor Connection","Serial controller is not available."); return
        if controller.connected: return
        if controller.connect():
            self.serial_status.setText("MOTOR: CONNECTED  /dev/ttyACM0 @ 57600"); self.serial_connect_button.setEnabled(False); self.serial_disconnect_button.setEnabled(True)
        else:
            self.serial_status.setText("MOTOR: CONNECTION FAILED  /dev/ttyACM0"); self.serial_connect_button.setEnabled(True); self.serial_disconnect_button.setEnabled(False)
    def disconnect_motor_serial(self):
        controller=getattr(self,"serial_controller",None)
        if controller is None: controller=getattr(getattr(self,"breakin_controller",None),"serial_controller",None)
        if controller is not None:
            try:
                if controller.connected: controller.stop_breakin()
            except Exception: logger.exception("Failed to stop motor before disconnect")
            controller.disconnect()
        self.serial_status.setText("MOTOR: DISCONNECTED  /dev/ttyACM0"); self.serial_connect_button.setEnabled(True); self.serial_disconnect_button.setEnabled(False)
    def _build_battery_db_button(self):
        layout, content=self._content_layout()
        if layout is None: return
        button=QPushButton("BATTERY DATABASE / INSTANCE & RESULT REGISTRATION",content); button.setMinimumHeight(44); button.setEnabled(True); button.clicked.connect(self.open_battery_database); layout.addWidget(button); self.battery_database_button=button
    def open_battery_database(self):
        dialog=BatteryDatabaseDialog(self.db_path,self); dialog.exec_()
    def _build_estimated_result_panel(self):
        content=self.centralWidget(); layout=content.layout() if content is not None else None
        if layout is None: return
        self.estimated_result={"UNLOADED_RPM":QLabel("--"),"TORQUE":QLabel("--"),"BRUSH_SCORE":QLabel("--"),"WEIGHT":QLabel("--")}
        box=QGroupBox("ESTIMATED PERFORMANCE / 推定値"); grid=QGridLayout(box)
        labels=(("無負荷回転数（推定）","UNLOADED_RPM"),("トルク（推定）","TORQUE"),("ブラシピーク（解析）","BRUSH_SCORE"),("対応車重（暫定推定）","WEIGHT"))
        for index,(title,key) in enumerate(labels):
            card=QGroupBox(title); card_layout=QGridLayout(card); value=self.estimated_result[key]; value.setAlignment(Qt.AlignCenter); value.setStyleSheet("font-size:16px;font-weight:bold;"); card_layout.addWidget(value,0,0); grid.addWidget(card,index//2,index%2)
        layout.addWidget(box)
    @staticmethod
    def _as_float(value,default=0.0):
        try: return float(value)
        except (TypeError,ValueError): return default
    @staticmethod
    def _measurement_value(measurement,*names):
        if isinstance(measurement,dict):
            for name in names:
                value=measurement.get(name)
                if value is not None: return value
        else:
            for name in names:
                value=getattr(measurement,name,None)
                if value is not None: return value
        return None
    def _measurement_series(self):
        controller=self.breakin_controller; return list(getattr(controller,"measurements",[]) or []) if controller else []
    def _analysis_series(self):
        data=getattr(self,"last_result_data",None)
        if isinstance(data,list): return [item for item in data if hasattr(item,"performance")]
        return [data] if hasattr(data,"performance") else []
    def _estimated_values(self):
        """Use AnalysisEngine outputs instead of duplicating provisional formulas in the UI.

        Display precision reflects the resolution of the source measurements; it does
        not imply calibration accuracy. Weight remains provisional until the physical
        vehicle-suitability model is calibrated against real chassis data.
        """
        analyses=self._analysis_series()
        if not analyses:
            return "データ不足", "データ不足", "データ不足", "校正データ不足"

        rpm_values=[self._as_float(getattr(a.performance.estimated_no_load_rpm,"value",None),0.0) for a in analyses]
        torque_values=[self._as_float(getattr(a.performance.estimated_torque,"value",None),0.0) for a in analyses]
        weight_values=[self._as_float(getattr(a.performance.estimated_supported_weight,"value",None),0.0) for a in analyses]
        rpm_values=[v for v in rpm_values if v>0]
        torque_values=[v for v in torque_values if v>0]
        weight_values=[v for v in weight_values if v>0]

        rpm=(sum(rpm_values)/len(rpm_values)) if rpm_values else 0.0
        torque=(sum(torque_values)/len(torque_values)) if torque_values else 0.0
        weight=(sum(weight_values)/len(weight_values)) if weight_values else 0.0

        brush_scores=[]
        brush_conditions=[]
        brush_peaks=[]
        for analysis in analyses:
            brush=getattr(analysis,"brush",None)
            if brush is None: continue
            score=self._as_float(getattr(getattr(brush,"peak_score",None),"value",None),0.0)
            peak=self._as_float(getattr(getattr(brush,"peak_position",None),"value",None),0.0)
            brush_scores.append(score)
            if peak>0: brush_peaks.append(peak)
            condition=str(getattr(brush,"brush_condition","UNKNOWN") or "UNKNOWN")
            brush_conditions.append(condition)

        if brush_scores:
            brush_score=sum(brush_scores)/len(brush_scores)
            peak=max(brush_peaks) if brush_peaks else 0.0
            condition=max(set(brush_conditions), key=brush_conditions.count) if brush_conditions else "UNKNOWN"
            brush_text=f"{brush_score:+.1f} / 10　{condition}　peak {peak:.3f} A" if peak>0 else f"{brush_score:+.1f} / 10　{condition}"
        else:
            brush_text="データ不足"

        rpm_text=f"{rpm:,.0f} rpm" if rpm>0 else "データ不足"
        torque_text=f"{torque:.2f} g·cm" if torque>0 else "データ不足"
        # Do not invent a 115–155 g range. The current weight conversion is explicitly
        # provisional in the Analysis module, so show the derived value and its status.
        weight_text=f"{weight:,.0f} g（暫定）" if weight>0 else "校正データ不足"
        return rpm_text,torque_text,brush_text,weight_text
    def _refresh_estimated_values(self):
        if not hasattr(self,"estimated_result"): return
        rpm,torque,brush_text,weight_text=self._estimated_values(); self.estimated_result["UNLOADED_RPM"].setText(rpm); self.estimated_result["TORQUE"].setText(torque); self.estimated_result["BRUSH_SCORE"].setText(brush_text); self.estimated_result["WEIGHT"].setText(weight_text)
    def complete(self,data,benchmark):
        super().complete(data,benchmark); self._refresh_estimated_values()
    def failed(self,message):
        super().failed(message)
        if hasattr(self,"estimated_result"):
            for value in self.estimated_result.values(): value.setText("NOT AVAILABLE")

class ApplicationRuntimeBuilder:
    SERIAL_PORT="/dev/ttyACM0"; SERIAL_BAUDRATE=57600
    def __init__(self): self.serial_controller=None
    def build_context(self):
        # Controller is created but deliberately NOT connected during application startup.
        self.serial_controller=SerialController(serial_port=self.SERIAL_PORT,baudrate=self.SERIAL_BAUDRATE)
        builder=ApplicationBuilder(serial_controller=self.serial_controller)
        return {"serial_controller":self.serial_controller,"breakin_controller":builder.build_breakin_controller(),"serial_connected":False}
    def close(self):
        if self.serial_controller is None: return
        try:
            if self.serial_controller.connected: self.serial_controller.stop_breakin()
        except Exception: logger.exception("Failed to stop Arduino during shutdown")
        finally:
            try: self.serial_controller.disconnect()
            except Exception: logger.exception("Failed to disconnect Arduino serial port")

def setup_logger():
    logger.remove(); logger.add(sys.stdout,level="INFO",colorize=True); logger.add(LOG_DIR/"system.log",rotation="10 MB",retention=10,encoding="utf-8",level="DEBUG")

def main():
    setup_logger(); app=QApplication(sys.argv); app.setApplicationName(APP_NAME); app.setApplicationVersion(APP_VERSION); runtime=ApplicationRuntimeBuilder()
    try:
        context=runtime.build_context(); window=MainWindow(context); window.show(); app.aboutToQuit.connect(runtime.close); return app.exec()
    except Exception:
        logger.exception("Fatal Error"); runtime.close(); QMessageBox.critical(None,"Fatal Error","致命的なエラーが発生しました。\nsystem.log を確認してください。"); return 1

if __name__=="__main__": sys.exit(main())
