# ============================================================
# device_type.py
# ============================================================

from enum import Enum


class DeviceType(str, Enum):

    BREAKIN = "BREAKIN"

    EVALUATION = "EVALUATION"

    MANUAL = "MANUAL"

    REFERENCE = "REFERENCE"

