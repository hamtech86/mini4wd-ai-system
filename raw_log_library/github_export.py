"""Manual GitHub registration for Local-first Raw Logs."""
from __future__ import annotations
import base64, json, os, urllib.error, urllib.request
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict
from .manager import RawLogLibrary

DEFAULT_REPOSITORY="hamtech86/mini4wd-raw-logs"
DEFAULT_API="https://api.github.com"
TOKEN_ENV="MINI4WD_GITHUB_TOKEN"

class GitHubRegistrationError(RuntimeError):
    pass

class GitHubRawLogExporter:
    def __init__(self, library:RawLogLibrary, repository:str=DEFAULT_REPOSITORY,
                 token:str|None=None, api_base:str=DEFAULT_API)->None:
        self.library=library; self.repository=repository
        self.token=token or os.getenv(TOKEN_ENV); self.api_base=api_base.rstrip("/")

    def register(self, log_id:str)->Dict[str,Any]:
        if not self.token:
            raise GitHubRegistrationError(f"GitHub token is not configured. Set {TOKEN_ENV} in the application environment.")
        status=self.library.get_github_status(log_id)
        if status.get("status")=="REGISTERED":
            raise GitHubRegistrationError(f"{log_id} is already registered on GitHub.")
        record,raw_path,_=self.library.get(log_id)
        metadata=asdict(record)
        metadata.pop("history_registered", None)
        metadata.update(registered_at=datetime.now(timezone.utc).isoformat(),
                        repository=self.repository)

        try:
            if raw_path.suffix == ".v2ref":
                package_dir = self.library.root.parent / "raw_logs_v2" / log_id
                manifest_path = package_dir / "manifest.json"
                records_path = package_dir / "records.jsonl"
                if not manifest_path.is_file() or not records_path.is_file():
                    raise GitHubRegistrationError(f"{log_id}: RawLog v2 package files are incomplete.")
                manifest_text = manifest_path.read_text(encoding="utf-8")
                manifest = json.loads(manifest_text)
                if manifest.get("status") == "STARTED":
                    raise GitHubRegistrationError(f"{log_id}: package is still STARTED; finalize or recover it before GitHub registration.")
                records_text = records_path.read_text(encoding="utf-8")
                remote_base = f"{record.device_type.lower()}/{self._individual_storage_id(record)}/{log_id}"
                remote_manifest = f"{remote_base}/manifest.json"
                remote_records = f"{remote_base}/records.jsonl"
                raw_result = self._put_file(
                    remote_manifest, manifest_text, f"Register RawLog v2 manifest {log_id}", allow_update=False
                )
                records_result = self._put_file(
                    remote_records, records_text, f"Register RawLog v2 records {log_id}", allow_update=False
                )
                raw_rel = remote_records
                metadata_rel = self._metadata_path(record)
                metadata.update(raw_source=str(package_dir), raw_path=raw_rel,
                                manifest_path=remote_manifest, metadata_path=metadata_rel)
            else:
                raw_body=self.library.read_raw(log_id)
                raw_rel=self._raw_path(record)
                metadata_rel=self._metadata_path(record)
                metadata.update(raw_source=str(raw_path),raw_path=raw_rel,metadata_path=metadata_rel)
                raw_result=self._put_file(raw_rel,raw_body,f"Register Raw Log {log_id}",allow_update=False)
                records_result=raw_result

            metadata_result=self._put_file(
                metadata_rel,json.dumps(metadata,ensure_ascii=False,indent=2)+"\\n",
                f"Register Metadata {log_id}",allow_update=False
            )
        except Exception as exc:
            self.library.set_github_status(log_id,status="FAILED",error=str(exc))
            if isinstance(exc, GitHubRegistrationError):
                raise
            raise GitHubRegistrationError(str(exc)) from exc
        commit=metadata_result.get("commit",{}).get("sha") or records_result.get("commit",{}).get("sha") or raw_result.get("commit",{}).get("sha")
        result={"status":"REGISTERED","repository":self.repository,"raw_path":raw_rel,
                "metadata_path":metadata_rel,"commit":commit,"registered_at":metadata["registered_at"]}
        self.library.set_github_status(log_id,**result)
        return result

    def _individual_storage_id(self, record):
        kind = record.device_type.lower()
        if kind == "motor":
            # Instance linkage is the authoritative physical-motor identity.
            # motor_id is retained as legacy metadata and must not determine storage
            # after a RawLog has been relinked to another Instance.
            individual_id = record.device_instance_id or record.motor_id
        else:
            individual_id = record.battery_id
        if not individual_id:
            raise GitHubRegistrationError(f"{record.log_id}: individual ID is missing.")
        return individual_id

    def _raw_path(self,record):
        kind=record.device_type.lower()
        individual_id=self._individual_storage_id(record)
        return f"{kind}/{individual_id}/{record.log_id}/raw.log"

    def _metadata_path(self,record):
        kind=record.device_type.lower()
        individual_id=self._individual_storage_id(record)
        return f"{kind}/{individual_id}/{record.log_id}/metadata.json"

    def _put_file(self,path,content,message,*,allow_update):
        url=f"{self.api_base}/repos/{self.repository}/contents/{path}"
        payload={"message":message,"content":base64.b64encode(content.encode("utf-8")).decode("ascii")}
        existing_sha=self._existing_sha(url)
        if existing_sha:
            if not allow_update: raise GitHubRegistrationError(f"GitHub target already exists: {path}. Duplicate registration was blocked.")
            payload["sha"]=existing_sha
        request=urllib.request.Request(url,data=json.dumps(payload).encode(),method="PUT",
            headers={"Accept":"application/vnd.github+json","Authorization":f"Bearer {self.token}",
                     "X-GitHub-Api-Version":"2026-03-10","Content-Type":"application/json",
                     "User-Agent":"mini4wd-ai-system-raw-log-exporter"})
        try:
            with urllib.request.urlopen(request,timeout=30) as response: return json.loads(response.read().decode())
        except urllib.error.HTTPError as exc:
            detail=exc.read().decode("utf-8",errors="replace")
            raise GitHubRegistrationError(f"GitHub API error {exc.code} for {path}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise GitHubRegistrationError(f"GitHub network error for {path}: {exc.reason}") from exc

    def _existing_sha(self,url):
        request=urllib.request.Request(url,method="GET",headers={"Accept":"application/vnd.github+json",
            "Authorization":f"Bearer {self.token}","X-GitHub-Api-Version":"2026-03-10",
            "User-Agent":"mini4wd-ai-system-raw-log-exporter"})
        try:
            with urllib.request.urlopen(request,timeout=15) as response: return json.loads(response.read().decode()).get("sha")
        except urllib.error.HTTPError as exc:
            if exc.code==404:return None
            detail=exc.read().decode("utf-8",errors="replace")
            raise GitHubRegistrationError(f"GitHub lookup error {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise GitHubRegistrationError(f"GitHub network error during lookup: {exc.reason}") from exc
