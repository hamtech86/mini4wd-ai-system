# ============================================================
# quality_status.py
# ============================================================

from enum import Enum


class QualityStatus(str, Enum):

    GOOD = "GOOD"

    WARNING = "WARNING"

    ERROR = "ERROR"

    INVALID = "INVALID"


---

④ anomaly_type.py

# ============================================================
# anomaly_type.py
# ============================================================

from enum import Enum


class AnomalyType(str, Enum):

    NONE = "NONE"

    RANDOM = "RANDOM"

    DEVICE = "DEVICE"

    OBJECT = "OBJECT"

    UNKNOWN = "UNKNOWN"

