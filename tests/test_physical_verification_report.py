import base64
import json
import urllib.error
from pathlib import Path

import pytest

from ui.physical_verification_report import PhysicalVerificationReport


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def _reporter():
    return PhysicalVerificationReport.__new__(PhysicalVerificationReport)


def test_upload_directory_sends_every_local_file_without_changing_local_bundle(tmp_path, monkeypatch):
    monkeypatch.setenv("MINI4WD_GITHUB_TOKEN", "test-token")
    bundle = tmp_path / "VERIFY-TEST"
    (bundle / "raw-logs").mkdir(parents=True)
    (bundle / "report.json").write_text('{"run":"VERIFY-TEST"}\n', encoding="utf-8")
    (bundle / "raw-logs" / "MOTOR-000001.log").write_bytes(b"DATA,1,2\r\n")
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return _Response()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    _reporter()._upload_directory(bundle, "VERIFY-TEST")

    assert len(requests) == 2
    assert all(timeout == 30 for _, timeout in requests)
    assert all("verification/runs/VERIFY-TEST/" in request.full_url for request, _ in requests)
    raw_request = next(request for request, _ in requests if request.full_url.endswith("MOTOR-000001.log"))
    payload = json.loads(raw_request.data.decode("utf-8"))
    assert base64.b64decode(payload["content"]) == b"DATA,1,2\r\n"
    assert (bundle / "raw-logs" / "MOTOR-000001.log").read_bytes() == b"DATA,1,2\r\n"


def test_upload_failure_leaves_local_bundle_intact(tmp_path, monkeypatch):
    monkeypatch.setenv("MINI4WD_GITHUB_TOKEN", "test-token")
    bundle = tmp_path / "VERIFY-FAILED"
    bundle.mkdir()
    report = bundle / "report.json"
    report.write_text('{"run":"VERIFY-FAILED"}\n', encoding="utf-8")

    def fail_urlopen(request, timeout):
        raise urllib.error.HTTPError(request.full_url, 403, "forbidden", {}, None)

    monkeypatch.setattr("urllib.request.urlopen", fail_urlopen)
    with pytest.raises(RuntimeError, match="GitHub API error 403"):
        _reporter()._upload_directory(bundle, "VERIFY-FAILED")

    assert report.exists()
    assert json.loads(report.read_text(encoding="utf-8"))["run"] == "VERIFY-FAILED"


def test_upload_requires_token_and_keeps_local_bundle(tmp_path, monkeypatch):
    monkeypatch.delenv("MINI4WD_GITHUB_TOKEN", raising=False)
    bundle = tmp_path / "VERIFY-NO-TOKEN"
    bundle.mkdir()
    report = bundle / "report.json"
    report.write_text("local evidence", encoding="utf-8")

    with pytest.raises(RuntimeError, match="MINI4WD_GITHUB_TOKEN"):
        _reporter()._upload_directory(bundle, "VERIFY-NO-TOKEN")

    assert report.read_text(encoding="utf-8") == "local evidence"
