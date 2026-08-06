"""
MINI4WD AI SYSTEM
Application Context

Runtime dependency container.
"""

from dataclasses import dataclass


@dataclass
class ApplicationContext:
    """Shared application services."""

    breakin_controller: object = None
    measurement_manager: object = None
    analysis_engine: object = None
    serial_controller: object = None
