"""
MINI4WD AI SYSTEM
MOTOR_BREAKIN_V3

Production application dependency builder.

This module is intentionally separate from the legacy ApplicationBuilder so
runtime DB wiring can be validated without altering existing test fixtures.
"""

from analysis.analysis_engine import AnalysisEngine
from communication.serial_controller import SerialController
from controllers.breakin_controller import BreakinController
from measurement.measurement_manager import MeasurementManager
from database.manager.database_manager import DatabaseManager
from database.manager.migration import Migration
from database.manager.session_manager import SessionManager
from database.repository.measurement_repository import MeasurementRepository


class ProductionApplicationBuilder:
    """Build the complete production break-in dependency graph."""

    def __init__(self, serial_controller, database_path="database/mini4wd.db"):
        self.serial_controller = serial_controller
        self.database = DatabaseManager(database_path)

    def initialize_database(self):
        Migration(self.database).migrate()
        return self.database

    def build_breakin_controller(self):
        self.initialize_database()

        measurement_manager = MeasurementManager(
            serial_controller=self.serial_controller
        )
        session_manager = SessionManager(self.database)
        measurement_repository = MeasurementRepository(self.database)

        return BreakinController(
            serial_controller=self.serial_controller,
            measurement_manager=measurement_manager,
            analysis_engine=AnalysisEngine(),
            database=self.database,
            session_manager=session_manager,
            measurement_repository=measurement_repository,
        )
