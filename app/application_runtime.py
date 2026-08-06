"""
MINI4WD AI SYSTEM
MOTOR_BREAKIN_V3

Application Runtime Wiring

Creates the runtime objects required by the temporary UI.
"""

from app.application_context import ApplicationContext
from app.application_builder import ApplicationBuilder


class ApplicationRuntime:
    """Build and expose application services."""

    def __init__(self, serial_controller, analysis_engine=None,
                 session_manager=None, database=None):
        self.builder = ApplicationBuilder(
            serial_controller=serial_controller,
            analysis_engine=analysis_engine,
            session_manager=session_manager,
            database=database,
        )

    def create_context(self):
        breakin_controller = self.builder.build_breakin_controller()

        return ApplicationContext(
            breakin_controller=breakin_controller,
            measurement_manager=breakin_controller.measurement_manager,
            analysis_engine=self.builder.analysis_engine,
            serial_controller=self.builder.serial_controller,
        )
