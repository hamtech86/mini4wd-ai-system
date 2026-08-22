"""MINI4WD AI SYSTEM / MOTOR_BREAKIN_V3 application entry point."""
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path: sys.path.insert(0, str(PROJECT_ROOT))
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMessageBox, QGroupBox, QGridLayout, QLabel, QPushButton, QScrollArea
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
        super().__init__(context); bind_resume_api(type(self)); install_resume_controls(self); self._build_estimated_result_panel(); self._build_battery_db_button()
    def _build_battery_db_button(self):
        central = self.centralWidget()
        scroll = central.findChild(QScrollArea) if central is not None else None
        content = scroll.widget() if scroll is not None else None
        layout = content.layout() if content is not None else None
        if layout is None: return
        button = QPushButton("BATTERY DATABASE / INSTANCE & RESULT REGISTRATION", content)
        button.setMinimumHeight(44)
        button.setEnabled(True)
        button.clicked.connect(self.open_battery_database)
        layout.addWidget(button)
        self.battery_database_button = button
    def open_battery_database(self):
        dialog=BatteryDatabaseDialog(self.db_path, self); dialog.exec_()
    def _build_estimated_result_panel(self):
        content=self.centralWidget(); layout=content.layout() if content is not None else None
        if layout is None: return
        self.estimated_result={"UNLOADED_RPM":QLabel("--"),"TORQUE":QLabel("--"),"BRUSH_SCORE":QLabel("--"),"WEIGHT":QLabel("--")}
        box=QGroupBox("ESTIMATED PERFORMANCE / 推定値"); grid=QGridLayout(box)
        labels=(("無負荷回転数（推定）","UNLOADED_RPM"),("トルク（推定）","TORQUE"),("ブラシピーク（推定）","BRUSH_SCORE"),("対応車重（推定）","WEIGHT"))
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
    def _estimated_values(self):
        measurements=self._measurement_series(); voltages=[self._as_float(self._measurement_value(m,"motor_voltage","voltage"),0.0) for m in measurements]; currents=[abs(self._as_float(self._measurement_value(m,"current_avg","current","current1"),0.0)) for m in measurements]; voltages=[v for v in voltages if v>0.01]; currents=[a for a in currents if a>0.001]
        average_voltage=sum(voltages)/len(voltages) if voltages else 0.0; average_current=sum(currents)/len(currents) if currents else 0.0; peak_current=max(currents) if currents else 0.0; estimated_rpm=max(0.0,average_voltage*5000.0); estimated_torque=max(0.0,average_current*10.0)
        if estimated_torque>0:
            reference_weight=estimated_torque*12.0; recommended_min=max(115.0,reference_weight-10.0); recommended_max=min(155.0,reference_weight+10.0); recommended_max=max(recommended_max,recommended_min); weight_text=f"{recommended_min:.0f}～{recommended_max:.0f} g"
        else: weight_text="データ不足"
        brush_score=max(-10.0,min(10.0,10.0-peak_current*5.0)) if currents else None
        if brush_score is None: brush_text="データ不足"
        elif brush_score>=7.0: brush_text=f"{brush_score:+.1f} / 10　新品寄り"
        elif brush_score>=2.0: brush_text=f"{brush_score:+.1f} / 10　馴染み中"
        elif brush_score>-2.0: brush_text=f"{brush_score:+.1f} / 10　PEAK / 完璧"
        elif brush_score>-7.0: brush_text=f"{brush_score:+.1f} / 10　摩耗傾向"
        else: brush_text=f"{brush_score:+.1f} / 10　故障域"
        return estimated_rpm,estimated_torque,brush_text,weight_text
    def _refresh_estimated_values(self):
        if not hasattr(self,"estimated_result"): return
        rpm,torque,brush_text,weight_text=self._estimated_values(); self.estimated_result["UNLOADED_RPM"].setText(f"{rpm:,.0f} rpm" if rpm>0 else "データ不足"); self.estimated_result["TORQUE"].setText(f"{torque:.2f} g·cm" if torque>0 else "データ不足"); self.estimated_result["BRUSH_SCORE"].setText(brush_text); self.estimated_result["WEIGHT"].setText(weight_text)
    def complete(self,data,benchmark): super().complete(data,benchmark); self._refresh_estimated_values()
    def failed(self,message):
        super().failed(message)
        if hasattr(self,"estimated_result"):
            for value in self.estimated_result.values(): value.setText("NOT AVAILABLE")

class ApplicationRuntimeBuilder:
    SERIAL_PORT="/dev/ttyACM0"; SERIAL_BAUDRATE=57600
    def __init__(self): self.serial_controller=None
    def build_context(self):
        self.serial_controller=SerialController(serial_port=self.SERIAL_PORT,baudrate=self.SERIAL_BAUDRATE); connected=self.serial_controller.connect()
        if connected: logger.info("Arduino serial connected: {} @ {} baud",self.SERIAL_PORT,self.SERIAL_BAUDRATE)
        else: logger.warning("Arduino serial connection failed: {} @ {} baud",self.SERIAL_PORT,self.SERIAL_BAUDRATE)
        builder=ApplicationBuilder(serial_controller=self.serial_controller); return {"serial_controller":self.serial_controller,"breakin_controller":builder.build_breakin_controller(),"serial_connected":connected}
    def close(self):
        if self.serial_controller is None: return
        try:
            if self.serial_controller.connected: self.serial_controller.stop_breakin()
        except Exception: logger.exception("Failed to stop Arduino during shutdown")
        finally:
            try:
                self.serial_controller.disconnect()
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