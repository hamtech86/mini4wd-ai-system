# ============================================================
# session_result.py
# ============================================================

from enum import Enum


class SessionResult(str, Enum):

    COMPLETE = "COMPLETE"

    ERROR = "ERROR"

    TIMEOUT = "TIMEOUT"

    CANCEL = "CANCEL"

