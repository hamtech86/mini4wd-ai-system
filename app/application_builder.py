"""
MINI4WD AI SYSTEM
MOTOR_BREAKIN_V3

Application Builder

Responsible for creating and connecting:
SerialController
MeasurementManager
AnalysisEngine
BreakinController
DatabaseManager
"""

from analysis.analysis_engine import AnalysisEngine
from controllers.breakin_controller import BreakinController
from measurement.measurement_manager import MeasurementManager
from database.manager.database_manager import DatabaseManager


class ApplicationBuilder:
    """Create application service instances."""

    def __init__(self, serial_controller, analysis_engine=None,
                 session_manager=None, database=None):
        self.serial_controller = serial_controller
        self.analysis_engine = analysis_engine
        self.session_manager = session_manager
        self.database = database or DatabaseManager("database/mini4wd.db")
        self.database.connect()

    def build_breakin_controller(self):
        measurement_manager = MeasurementManager(
            serial_controller=self.serial_controller
        )

        analysis_engine = self.analysis_engine or AnalysisEngine()

        return BreakinController(
            serial_controller=self.serial_controller,
            measurement_manager=measurement_manager,
            analysis_engine=analysis_engine,
            database=self.database,
            session_manager=self.session_manager,
        )
