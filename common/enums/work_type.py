# ============================================================
# work_type.py
# ============================================================

from enum import Enum


class WorkType(str, Enum):

    INITIAL_BREAKIN = "INITIAL_BREAKIN"

    BREAKIN = "BREAKIN"

    PEAK_CHECK = "PEAK_CHECK"

    CLEANING = "CLEANING"

    CONTACT_REVIVER = "CONTACT_REVIVER"

    MAGNETIZATION = "MAGNETIZATION"

    DISASSEMBLY = "DISASSEMBLY"

    ASSEMBLY = "ASSEMBLY"

    REPAIR = "REPAIR"

    OTHER = "OTHER"

