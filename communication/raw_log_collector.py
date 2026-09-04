"""Raw serial-line collection for immutable session capture.

The collector is deliberately independent from CSVParser/Measurement.  It keeps
exactly the decoded lines received from SerialReader so the UI can export the
session raw log without reconstructing it from derived Measurement objects.
"""

from threading import Lock


class RawLogCollector:
    """In-memory raw-log buffer for the current serial connection session."""

    def __init__(self):
        self._lock = Lock()
        self._lines = []

    def reset(self):
        """Start a new capture buffer.

        This is a transport-level connection boundary for now.  The formal
        measurement-session definition remains a separate design item.
        """
        with self._lock:
            self._lines.clear()

    def append(self, raw_line: str):
        """Append one received line without parsing or reformatting it."""
        if raw_line is None:
            return
        with self._lock:
            self._lines.append(raw_line)

    @property
    def raw_text(self) -> str:
        """Return the captured raw text exactly as received by the reader."""
        with self._lock:
            return "".join(self._lines)

    @property
    def has_data(self) -> bool:
        with self._lock:
            return bool(self._lines)

    def snapshot(self) -> str:
        """Return a stable snapshot suitable for clipboard/export use."""
        return self.raw_text
