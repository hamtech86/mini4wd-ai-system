"""MINI4WD AI SYSTEM / MOTOR_BREAKIN_V3 application entry point."""
import sys
from pathlib import Path
PROJECT_ROOT=Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path: sys.path.insert(0,str(PROJECT_ROOT))
from PyQt5.QtWidgets import QApplication,QMessageBox
from loguru import logger
from config import APP_NAME,APP_VERSION,LOG_DIR
from ui.main_window import MainWindow
from communication.serial_controller import SerialController
from app.application_builder import ApplicationBuilder
class ApplicationRuntimeBuilder:
    SERIAL_PORT="/dev/ttyACM0"; SERIAL_BAUDRATE=57600
    def __init__(self): self.serial_controller=None
    def build_context(self):
        self.serial_controller=SerialController(serial_port=self.SERIAL_PORT,baudrate=self.SERIAL_BAUDRATE); connected=self.serial_controller.connect()
        logger.info("Arduino serial connected: {} @ {} baud",self.SERIAL_PORT,self.SERIAL_BAUDRATE) if connected else logger.warning("Arduino serial connection failed: {} @ {} baud",self.SERIAL_PORT,self.SERIAL_BAUDRATE)
        builder=ApplicationBuilder(serial_controller=self.serial_controller)
        return {"serial_controller":self.serial_controller,"breakin_controller":builder.build_breakin_controller(),"serial_connected":connected}
    def close(self):
        if self.serial_controller is None:return
        try:
            if self.serial_controller.connected:self.serial_controller.stop_breakin()
        except Exception:logger.exception("Failed to stop Arduino during shutdown")
        finally:
            try:self.serial_controller.disconnect()
            except Exception:logger.exception("Failed to disconnect Arduino serial port")
def setup_logger():
    logger.remove(); logger.add(sys.stdout,level="INFO",colorize=True); logger.add(LOG_DIR/"system.log",rotation="10 MB",retention=10,encoding="utf-8",level="DEBUG")
def main():
    setup_logger(); app=QApplication(sys.argv); app.setApplicationName(APP_NAME); app.setApplicationVersion(APP_VERSION); runtime=ApplicationRuntimeBuilder()
    try:
        context=runtime.build_context(); window=MainWindow(context); window.show(); app.aboutToQuit.connect(runtime.close); return app.exec()
    except Exception:
        logger.exception("Fatal Error"); runtime.close(); QMessageBox.critical(None,"Fatal Error","致命的なエラーが発生しました。\nsystem.log を確認してください。"); return 1
if __name__=="__main__":sys.exit(main())
