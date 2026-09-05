"""
MINI4WD AI SYSTEM
MOTOR_BREAKIN_V3

Application Builder

Responsible for creating and connecting:
SerialController
MeasurementManager
AnalysisEngine
BreakinController

The builder keeps dependency wiring outside individual modules.
"""

from analysis.analysis_engine import AnalysisEngine
from controllers.local_raw_log_breakin_controller import LocalRawLogBreakinController
from measurement.measurement_manager import MeasurementManager
from raw_log_library import RawLogLibrary


class ApplicationBuilder:
    """Create application service instances."""

    def __init__(self, serial_controller, analysis_engine=None,
                 session_manager=None, database=None, raw_log_library=None):
        self.serial_controller = serial_controller
        self.analysis_engine = analysis_engine
        self.session_manager = session_manager
        self.database = database
        self.raw_log_library = raw_log_library or RawLogLibrary()

    def build_breakin_controller(self):
        measurement_manager = MeasurementManager(
            serial_controller=self.serial_controller
        )

        analysis_engine = self.analysis_engine or AnalysisEngine()

        return LocalRawLogBreakinController(
            serial_controller=self.serial_controller,
            measurement_manager=measurement_manager,
            analysis_engine=analysis_engine,
            database=self.database,
            session_manager=self.session_manager,
            raw_log_library=self.raw_log_library,
        )
