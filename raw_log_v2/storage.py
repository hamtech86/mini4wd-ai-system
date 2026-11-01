"""Crash-safe RawLog v2 package writer and recovery."""
from __future__ import annotations
import hashlib, json, os, shutil, tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from .validator import validate_package, parse_complete_jsonl

class RawLogV2Error(RuntimeError): pass
class ExistingPackageError(RawLogV2Error): pass
class DurabilityError(RawLogV2Error): pass

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")

def _fsync_dir(path: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
    try:
        fd = os.open(str(path), flags)
        try: os.fsync(fd)
        finally: os.close(fd)
    except OSError as exc:
        raise DurabilityError(f"directory fsync unavailable for {path}: {exc}") from exc

def _write_new_file(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        view = memoryview(payload)
        while view:
            count = os.write(fd, view)
            if count <= 0: raise OSError("short write")
            view = view[count:]
        os.fsync(fd)
    finally: os.close(fd)
    _fsync_dir(path.parent)

def _publish_new_file(path: Path, payload: bytes, temp_path: Path) -> None:
    """Publish a new immutable file by hard-linking a fully fsynced staging file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ExistingPackageError(f"refusing symlink destination: {path}")
    if path.exists():
        if not path.is_file() or path.read_bytes() != payload:
            raise ExistingPackageError(f"existing immutable file differs: {path}")
        if temp_path.exists():
            if temp_path.is_symlink() or not temp_path.is_file():
                raise ExistingPackageError(f"invalid staging entry: {temp_path}")
            temp_path.unlink()
            _fsync_dir(temp_path.parent)
        # An earlier attempt may have linked this name and crashed before
        # syncing the parent directory. Reconfirm durability on every retry.
        _fsync_dir(path.parent)
        return
    if temp_path.exists():
        if temp_path.is_symlink() or not temp_path.is_file():
            raise ExistingPackageError(f"invalid staging entry: {temp_path}")
        if temp_path.read_bytes() != payload:
            temp_path.unlink()
            _fsync_dir(temp_path.parent)
    if not temp_path.exists():
        _write_new_file(temp_path, payload)
    try:
        os.link(temp_path, path)
    except FileExistsError:
        if not path.is_file() or path.read_bytes() != payload:
            raise ExistingPackageError(f"immutable destination appeared with different bytes: {path}")
    temp_path.unlink()
    _fsync_dir(path.parent)
    if temp_path.parent != path.parent:
        _fsync_dir(temp_path.parent)


def _atomic_replace_json(path: Path, value: Any) -> None:
    fd, name = tempfile.mkstemp(prefix=".state-", suffix=".tmp", dir=str(path.parent))
    temp = Path(name)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(_json_bytes(value)); stream.flush(); os.fsync(stream.fileno())
        os.replace(temp, path)
        _fsync_dir(path.parent)
    except Exception:
        try: temp.unlink()
        except FileNotFoundError: pass
        raise

def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def _snapshot_tree(source: Path) -> Tuple[List[Tuple[str, bytes]], str]:
    entries = []
    for path in sorted(source.rglob("*")):
        rel = path.relative_to(source).as_posix()
        if path.is_symlink(): raise RawLogV2Error(f"symlink in work area: {rel}")
        if path.is_dir(): continue
        if not path.is_file(): raise RawLogV2Error(f"unsupported work-area entry: {rel}")
        entries.append((rel, path.read_bytes()))
    digest = hashlib.sha256()
    for rel, payload in entries:
        digest.update(rel.encode("utf-8") + b"\0")
        digest.update(len(payload).to_bytes(8, "big")); digest.update(payload)
    return entries, digest.hexdigest()

def _read_recovery_records(raw: bytes):
    boundary = raw.rfind(b"\n") + 1
    complete, tail = raw[:boundary], raw[boundary:]
    accepted, records, rejected = [], [], []
    for number, line in enumerate(complete.splitlines(keepends=True), 1):
        if not line.endswith(b"\n") or line in (b"\n", b"\r\n"):
            rejected.append(f"line {number}: blank or unterminated"); continue
        try: record = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            rejected.append(f"line {number}: invalid JSON ({exc})"); continue
        if not isinstance(record, dict):
            rejected.append(f"line {number}: JSON value is not an object"); continue
        records.append(record); accepted.append(line)
    return b"".join(accepted), tail, records, rejected

class RawLogV2Writer:
    def __init__(self, root):
        self.root = Path(root); self.work_root = self.root / ".work"
        self.recovery_root = self.root / ".recovery"

    def begin(self, manifest_fields: Dict[str, Any]):
        missing = {"log_id", "measurement_session_id", "started_at_utc"} - set(manifest_fields)
        if missing: raise ValueError(f"missing session metadata: {sorted(missing)}")
        log_id = manifest_fields["log_id"]
        if not isinstance(log_id, str) or not log_id or Path(log_id).name != log_id:
            raise ValueError("log_id must be a non-empty path-safe string")
        if (self.root / log_id).exists(): raise ExistingPackageError(f"final package already exists: {log_id}")
        self.root.mkdir(parents=True, exist_ok=True)
        _fsync_dir(self.root.parent)
        self.work_root.mkdir(parents=True, exist_ok=True)
        _fsync_dir(self.root)
        work_dir = self.work_root / log_id
        work_dir.mkdir(exist_ok=False); _fsync_dir(self.work_root)
        _write_new_file(work_dir / "records.jsonl", b"")
        state = {"work_format":"rawlog-v2-work-state/1","phase":"recording",
            "log_id":log_id,"measurement_session_id":manifest_fields["measurement_session_id"],
            "manifest_fields":dict(manifest_fields),"created_at_utc":utc_now(),
            "record_count":0,"last_record_seq":0}
        _write_new_file(work_dir / "work_state.json", _json_bytes(state))
        return RawLogV2Session(self, work_dir, state)

    def list_incomplete_work(self) -> List[str]:
        """Discover pending work areas at startup without modifying any data."""
        if self.work_root.is_symlink():
            raise RawLogV2Error(".work root must not be a symlink")
        if not self.work_root.exists():
            return []
        if not self.work_root.is_dir():
            raise RawLogV2Error(".work root is not a directory")
        log_ids = []
        for child in sorted(self.work_root.iterdir(), key=lambda item: item.name):
            if child.is_symlink():
                raise RawLogV2Error(f"symlink in .work root: {child.name}")
            if not child.is_dir():
                raise RawLogV2Error(f"unexpected non-directory in .work root: {child.name}")
            log_ids.append(child.name)
        return log_ids

    def recover_pending(self) -> List[Dict[str, Any]]:
        """Run next-startup recovery for every discovered work area, in stable order."""
        return [self.recover_incomplete(log_id) for log_id in self.list_incomplete_work()]

    def _return_existing_recovery(self, log_id: str):
        parent = self.recovery_root / log_id
        if not parent.is_dir(): raise FileNotFoundError(f"no work area or recovery for {log_id}")
        matches = []
        for recovery_dir in parent.glob("crash-*"):
            rp = recovery_dir / "recovery_record.json"
            if not rp.is_file(): continue
            record = json.loads(rp.read_text(encoding="utf-8"))
            original = recovery_dir / "original"
            _, digest = _snapshot_tree(original)
            if digest != record.get("source_tree_sha256"):
                raise RawLogV2Error("preserved recovery original hash mismatch")
            # Reconfirm the entire preservation chain on every retry. This
            # covers a crash after hard-link publication but before directory
            # fsync, including the manifest-last commit point.
            original_dirs = sorted(
                (p for p in original.rglob("*") if p.is_dir()),
                key=lambda p: len(p.parts), reverse=True)
            for directory in original_dirs:
                _fsync_dir(directory)
            _fsync_dir(original)
            _fsync_dir(recovery_dir)
            _fsync_dir(parent)
            _fsync_dir(self.recovery_root)
            final = self.root / log_id
            mp, dp = final / "manifest.json", final / "records.jsonl"
            if not (mp.is_file() and dp.is_file()): continue
            if {p.name for p in final.iterdir()} != {"manifest.json", "records.jsonl"}: continue
            if _sha256(mp.read_bytes()) == record.get("final_manifest_sha256") and _sha256(dp.read_bytes()) == record.get("final_records_sha256"):
                _fsync_dir(final)
                matches.append(record)
        if len(matches) == 1: return matches[0]
        if len(matches) > 1: raise RawLogV2Error("multiple recovery records match the final package")
        raise FileNotFoundError(f"no verified completed recovery for {log_id}")

    def recover_incomplete(self, log_id: str, recovered_at_utc: Optional[str] = None):
        work_dir = self.work_root / log_id
        if not work_dir.is_dir(): return self._return_existing_recovery(log_id)
        final_dir = self.root / log_id
        if (final_dir / "manifest.json").is_file():
            # Manifest-last publication is the commit point. A crash after that
            # point must not downgrade an already committed package to incomplete.
            try:
                prior_recovery = self._return_existing_recovery(log_id)
            except FileNotFoundError:
                prior_recovery = None
            if prior_recovery is not None:
                if {p.name for p in final_dir.iterdir()} != {"manifest.json", "records.jsonl"}:
                    raise ExistingPackageError("recovered package contains unexpected files")
                shutil.rmtree(work_dir)
                _fsync_dir(self.work_root)
                return prior_recovery
            state = json.loads((work_dir / "work_state.json").read_text(encoding="utf-8"))
            intent = state.get("publication")
            records_path = final_dir / "records.jsonl"
            manifest_path = final_dir / "manifest.json"
            if ({p.name for p in final_dir.iterdir()} != {"manifest.json", "records.jsonl"}
                    or not isinstance(intent, dict) or not records_path.is_file()
                    or _sha256(records_path.read_bytes()) != intent.get("records_sha256")
                    or _sha256(manifest_path.read_bytes()) != intent.get("manifest_sha256")):
                raise ExistingPackageError("a final manifest exists but does not match this work area's publication intent")
            # Normal finalize may have linked manifest.json and crashed before
            # syncing this directory. Hash agreement proves content identity,
            # not durability of the directory entry; reconfirm it before the
            # work area can be marked published or removed.
            _fsync_dir(final_dir)
            state["phase"] = "published"
            _atomic_replace_json(work_dir / "work_state.json", state)
            shutil.rmtree(work_dir)
            _fsync_dir(self.work_root)
            return {"recovery_status": "already_published", "log_id": log_id,
                    "final_package_path": log_id, "manifest_sha256": intent["manifest_sha256"],
                    "records_sha256": intent["records_sha256"]}
        entries, tree_hash = _snapshot_tree(work_dir)
        recovery_id = "crash-" + tree_hash
        recovery_dir = self.recovery_root / log_id / recovery_id
        original_dir = recovery_dir / "original"
        self.root.mkdir(parents=True, exist_ok=True)
        self.recovery_root.mkdir(parents=True, exist_ok=True)
        _fsync_dir(self.root)
        recovery_log_dir = self.recovery_root / log_id
        recovery_log_dir.mkdir(parents=True, exist_ok=True)
        _fsync_dir(self.recovery_root)
        recovery_dir.mkdir(exist_ok=True); _fsync_dir(recovery_dir.parent)
        original_dir.mkdir(exist_ok=True); _fsync_dir(recovery_dir)
        expected_paths = {rel for rel, _ in entries}
        for path in original_dir.rglob("*"):
            if path.is_symlink(): raise RawLogV2Error("symlink found in recovery originals")
            if path.is_file() and path.relative_to(original_dir).as_posix() not in expected_paths:
                raise RawLogV2Error("unexpected file in recovery originals")
        for rel, payload in entries:
            target = original_dir / rel
            staging_key = _sha256(rel.encode("utf-8") + b"\\0" + payload)
            staging = recovery_dir / (".preserve-" + staging_key + ".tmp")
            _publish_new_file(target, payload, staging)
        _, preserved_hash = _snapshot_tree(original_dir)
        if preserved_hash != tree_hash: raise RawLogV2Error("recovery original verification failed")
        _fsync_dir(original_dir)

        raw_records_path = work_dir / "records.jsonl"
        raw_records = raw_records_path.read_bytes() if raw_records_path.exists() else b""
        recovered_jsonl, tail, records, rejected = _read_recovery_records(raw_records)
        state = json.loads((work_dir / "work_state.json").read_text(encoding="utf-8"))
        if state.get("log_id") != log_id or not isinstance(state.get("manifest_fields"), dict):
            raise RawLogV2Error("work_state.json identity/manifest_fields invalid")

        recovery_record_path = recovery_dir / "recovery_record.json"
        if recovery_record_path.exists():
            recovery_record = json.loads(recovery_record_path.read_text(encoding="utf-8"))
            if recovery_record.get("source_tree_sha256") != tree_hash:
                raise RawLogV2Error("recovery record points to different original bytes")
            recovery_time = recovery_record["recovered_at_utc"]
        else:
            recovery_time = recovered_at_utc or utc_now()

        counts = {}
        for item in records:
            kind = item.get("record_type")
            if isinstance(kind, str): counts[kind] = counts.get(kind, 0) + 1
        manifest = dict(state["manifest_fields"])
        manifest.update({"created_at_utc":recovery_time,"ended_at_utc":None,"status":"incomplete",
            "planned_stage_count":31,"planned_stage_duration_ms":10000,
            "planned_total_duration_ms":310000,"record_counts":counts})
        validation = validate_package(manifest, records, raise_on_error=False)

        if not recovery_record_path.exists():
            recovery_record = {"recovery_format":"rawlog-v2-recovery-record/1",
                "recovery_id":recovery_id,"log_id":log_id,
                "measurement_session_id":state.get("measurement_session_id"),
                "recovered_at_utc":recovery_time,"source_work_directory":f".work/{log_id}",
                "source_tree_sha256":tree_hash,
                "preserved_files":[{"path":rel,"size_bytes":len(payload),"sha256":_sha256(payload)} for rel,payload in entries],
                "source_records_sha256":_sha256(raw_records),"complete_json_record_count":len(records),
                "incomplete_tail_present":bool(tail),"incomplete_tail_size_bytes":len(tail),
                "incomplete_tail_sha256":_sha256(tail) if tail else None,
                "rejected_complete_lines":rejected,"validation_errors":validation,
                "final_package_path":log_id,"final_records_sha256":_sha256(recovered_jsonl),
                "final_manifest_sha256":_sha256(_json_bytes(manifest))}
            recovery_record_bytes = _json_bytes(recovery_record)
            _publish_new_file(recovery_record_path, recovery_record_bytes,
                recovery_dir / ".recovery-record.tmp")
        else:
            if recovery_record.get("final_records_sha256") != _sha256(recovered_jsonl):
                raise RawLogV2Error("recovery record final records hash does not match source")
            if recovery_record.get("final_manifest_sha256") != _sha256(_json_bytes(manifest)):
                raise RawLogV2Error("recovery record final manifest hash does not match source")

        publication_state = recovery_dir / "publication_state.json"
        if not publication_state.exists():
            _atomic_replace_json(publication_state, {"phase":"recording","publication":None,
                "source_tree_sha256":tree_hash})
        self._publish_package(self.root / log_id, work_dir, recovered_jsonl, manifest,
            recovery_id, state_path=publication_state)
        shutil.rmtree(work_dir); _fsync_dir(self.work_root)
        return recovery_record

    def _publish_package(self, final_dir: Path, work_dir: Path, records_bytes: bytes,
                         manifest: Dict[str, Any], publication_id: str, state_path: Optional[Path]=None):
        manifest_bytes = _json_bytes(manifest)
        state_path = state_path or (work_dir / "work_state.json")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        intent = {"phase":"publishing","publication_id":publication_id,
            "records_sha256":_sha256(records_bytes),"manifest_sha256":_sha256(manifest_bytes)}
        if state.get("publication") not in (None, intent):
            raise ExistingPackageError("different publication intent already exists")
        if state.get("publication") is None:
            state["publication"] = intent; _atomic_replace_json(state_path, state)
        if not final_dir.exists():
            final_dir.mkdir(); _fsync_dir(final_dir.parent)
        elif not final_dir.is_dir(): raise ExistingPackageError("final path is not a directory")

        records_temp_name = ".records-" + publication_id + ".tmp"
        manifest_temp_name = ".manifest-" + publication_id + ".tmp"
        allowed_names = {"manifest.json", "records.jsonl", records_temp_name, manifest_temp_name}
        for child in final_dir.iterdir():
            if child.name not in allowed_names or child.is_symlink() or not child.is_file():
                raise ExistingPackageError(f"unexpected entry in final package directory: {child.name}")

        records_path = final_dir / "records.jsonl"
        _publish_new_file(records_path, records_bytes, final_dir / records_temp_name)

        manifest_path = final_dir / "manifest.json"
        _publish_new_file(manifest_path, manifest_bytes, final_dir / manifest_temp_name)
        if records_path.read_bytes() != records_bytes or manifest_path.read_bytes() != manifest_bytes:
            raise RawLogV2Error("published package verification failed")
        if {p.name for p in final_dir.iterdir()} != {"manifest.json", "records.jsonl"}:
            raise RawLogV2Error("final package must contain exactly manifest.json and records.jsonl")
        state["phase"] = "published"; _atomic_replace_json(state_path, state)


class RawLogV2Session:
    def __init__(self, writer, work_dir: Path, state: Dict[str, Any]):
        self.writer, self.work_dir, self.state = writer, work_dir, state
        self.records_path, self.state_path = work_dir / "records.jsonl", work_dir / "work_state.json"
        self.closed = False

    def append(self, record: Dict[str, Any]):
        if self.closed or self.state.get("phase") != "recording": raise RawLogV2Error("session is not appendable")
        expected = int(self.state["last_record_seq"]) + 1
        if record.get("record_seq") != expected: raise ValueError(f"record_seq must be continuous; expected {expected}")
        if record.get("log_id") != self.state["log_id"]: raise ValueError("record log_id does not match session")
        if record.get("measurement_session_id") != self.state["measurement_session_id"]:
            raise ValueError("record measurement_session_id does not match session")
        payload = _json_bytes(record)
        fd = os.open(str(self.records_path), os.O_WRONLY | os.O_APPEND)
        try:
            view = memoryview(payload)
            while view:
                count = os.write(fd, view)
                if count <= 0: raise OSError("short append to records.jsonl")
                view = view[count:]
            os.fsync(fd)
        finally: os.close(fd)
        self.state["record_count"] = expected; self.state["last_record_seq"] = expected
        _atomic_replace_json(self.state_path, self.state)

    def finalize(self, manifest_fields: Dict[str, Any], status: str, ended_at_utc: Optional[str]):
        if status not in {"completed", "aborted"}: raise ValueError("normal finalization status must be completed or aborted")
        if self.closed: raise RawLogV2Error("session is already closed")
        raw = self.records_path.read_bytes()
        records, parse_errors = parse_complete_jsonl(raw)
        if parse_errors: raise RawLogV2Error("malformed JSONL: " + "; ".join(parse_errors))
        if len(records) != self.state["record_count"]: raise RawLogV2Error("work_state record_count differs from records")
        manifest = dict(self.state["manifest_fields"]); manifest.update(manifest_fields)
        counts = {}
        for item in records:
            kind = item.get("record_type")
            if isinstance(kind, str): counts[kind] = counts.get(kind, 0) + 1
        manifest.update({"created_at_utc":utc_now(),"ended_at_utc":ended_at_utc,"status":status,
            "planned_stage_count":31,"planned_stage_duration_ms":10000,
            "planned_total_duration_ms":310000,"record_counts":counts})
        errors = validate_package(manifest, records, raise_on_error=False)
        if errors: raise RawLogV2Error("manifest/records validation failed: " + "; ".join(errors))
        final_dir = self.writer.root / manifest["log_id"]
        self.writer._publish_package(final_dir, self.work_dir, raw, manifest, "normal-" + _sha256(raw))
        self.closed = True; shutil.rmtree(self.work_dir); _fsync_dir(self.writer.work_root)
        return final_dir
