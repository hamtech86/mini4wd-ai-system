import tempfile
import json
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


    def test_github_paths_follow_relinked_motor_instance(self):
        with tempfile.TemporaryDirectory() as tmp:
            library = RawLogLibrary(tmp)
            record = RawLog(
                device_type="MOTOR",
                motor_id="14",
                device_instance_id="7",
            )
            library.register(record, "RAW\n")
            exporter = GitHubRawLogExporter(library, token="dummy")
            self.assertEqual(
                exporter._raw_path(record),
                f"motor/7/{record.log_id}/raw.log",
            )
            self.assertEqual(
                exporter._metadata_path(record),
                f"motor/7/{record.log_id}/metadata.json",
            )


    def test_v2_sidecars_and_manifest_are_exported_with_raw_log(self):
        from communication.rawlog_v2_aux import parse_aux_line

        with tempfile.TemporaryDirectory() as tmp:
            library = RawLogLibrary(tmp)
            record = RawLog(
                device_type="MOTOR",
                motor_id="123",
                device_instance_id="123",
                measurement_session_id="APP-SESSION-1",
            )
            library.register(record, "DATA," + ",".join(["0"] * 25) + "\\n")
            aux = [parse_aux_line(
                "AUX,2,FW-SESSION-1,1,WINDING,FWD,0,MEASURE,A0,512,1000"
            )]
            library.register_v2_aux(
                record.log_id, aux, [],
                measurement_session_id="APP-SESSION-1",
            )

            exporter = GitHubRawLogExporter(library, token="dummy")
            uploaded = []
            def fake_put(path, content, message, *, allow_update):
                uploaded.append((path, content, allow_update))
                return {"commit": {"sha": "fake-commit"}}
            exporter._put_file = fake_put

            result = exporter.register(record.log_id)

            prefix = f"motor/123/{record.log_id}/"
            paths = [item[0] for item in uploaded]
            self.assertEqual(paths[0], prefix + "raw.log")
            self.assertIn(prefix + f"{record.log_id}.aux.jsonl", paths)
            self.assertIn(prefix + f"{record.log_id}.manifest.json", paths)
            self.assertEqual(paths[-1], prefix + "metadata.json")
            self.assertTrue(all(item[2] is False for item in uploaded))
            manifest_upload = next(item for item in uploaded if item[0].endswith(".manifest.json"))
            self.assertEqual(json.loads(manifest_upload[1])["raw_body"], prefix + "raw.log")
            self.assertEqual(result["sidecar_paths"]["aux_records"], prefix + f"{record.log_id}.aux.jsonl")
            self.assertEqual(library.get_github_status(record.log_id)["status"], "REGISTERED")


if __name__ == "__main__":
    unittest.main()
