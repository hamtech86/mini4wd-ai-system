import tempfile
import unittest
from pathlib import Path

from raw_log_library import RawLog, RawLogLibrary
from raw_log_library.github_export import GitHubRawLogExporter


class RawLogGitHubTests(unittest.TestCase):
    def test_status_is_separate_from_raw_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = RawLogLibrary(tmp)
            record = RawLog(
                device_type="MOTOR",
                motor_id="123",
                device_instance_id="123",
                measurement_session_id="S1",
            )
            raw_path = library.register(record, "RAW,UNCHANGED\n")
            before = raw_path.read_text(encoding="utf-8")

            library.set_github_status(
                record.log_id,
                status="FAILED",
                error="network",
            )

            self.assertEqual(library.read_raw(record.log_id), before)
            self.assertEqual(library.get_github_status(record.log_id)["status"], "FAILED")

    def test_github_paths_are_log_id_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = RawLogLibrary(tmp)
            record = RawLog(
                device_type="MOTOR",
                motor_id="123",
                device_instance_id="123",
            )
            library.register(record, "RAW\n")
            exporter = GitHubRawLogExporter(library, token="dummy")
            self.assertEqual(
                exporter._raw_path(record),
                f"motor/123/{record.log_id}/raw.log",
            )
            self.assertEqual(
                exporter._metadata_path(record),
                f"motor/123/{record.log_id}/metadata.json",
            )


if __name__ == "__main__":
    unittest.main()
