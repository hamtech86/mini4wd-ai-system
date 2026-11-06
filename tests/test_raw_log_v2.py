import json
import pytest
from pathlib import Path
from raw_log_v2 import ExistingPackageError, RawLogV2Writer, validate_package

NOW = "2026-11-01T00:00:00.000Z"
END = "2026-11-01T00:01:00.000Z"

def manifest_fields(log_id="MOTOR-310-TEST"):
    return {
        "schema_name":"mini4wd.rawlog", "schema_version":"2.0.0", "log_id":log_id,
        "measurement_session_id":"SESSION-TEST", "measurement_type":"PWM_START_SWEEP_310S",
        "started_at_utc":NOW, "motor_instance_id":"7",
        "device":{"type":"MOTOR","model":"MOTOR_BREAKIN_V3","firmware_version":"3.x",
                  "firmware_build":"test-build","firmware_id":"000001","adc_resolution_bits":10},
        "measurement_conditions":{"direction":"FWD","voltage_control_mode":"INPUT",
            "sweep_pwm_min":0,"sweep_pwm_max":30,"stage_duration_ms":10000,"schedule_owner":"PYTHON"},
        "metadata_warnings":[]
    }

def session_event(log_id="MOTOR-310-TEST"):
    return {"schema_version":"2.0.0","record_type":"SESSION_EVENT","record_id":"event-start",
        "record_seq":1,"log_id":log_id,"measurement_session_id":"SESSION-TEST",
        "recorded_at_utc":NOW,"event":"SESSION_STARTED","host_monotonic_ns":1,
        "details":{"measurement_type":"PWM_START_SWEEP_310S"}}

def stage_record(index, log_id="MOTOR-310-TEST"):
    t=f"2026-11-01T00:00:{index:02d}.000Z"
    return {"schema_version":"2.0.0","record_type":"PWM_STAGE","record_id":f"stage-{index}",
        "record_seq":index+1,"log_id":log_id,"measurement_session_id":"SESSION-TEST",
        "recorded_at_utc":"2026-11-01T00:01:00.000Z","stage_id":f"PWM-{index:02d}",
        "stage_index":index,"pwm_command":index,"planned_duration_ms":10000,
        "stage_status":"completed","started_at_utc":t,
        "ended_at_utc":f"2026-11-01T00:00:{index:02d}.500Z",
        "start_host_monotonic_ns":index*1000000,"end_host_monotonic_ns":index*1000000+500000000,
        "actual_duration_ms":500,"pwm_command_sent_at_utc":t,
        "pwm_applied_ack_received_at_utc":t,"output_state":"unknown",
        "stage_context_id":f"context-{index}","termination_reason":"duration_elapsed"}

def test_normal_finalize_publishes_exactly_two_files(tmp_path):
    writer=RawLogV2Writer(tmp_path); session=writer.begin(manifest_fields())
    for i in range(31): session.append(stage_record(i))
    final=session.finalize({"ended_at_utc":END},"completed",END)
    assert sorted(p.name for p in final.iterdir())==["manifest.json","records.jsonl"]
    manifest=json.loads((final/"manifest.json").read_text())
    assert manifest["status"]=="completed" and manifest["record_counts"]=={"PWM_STAGE":31}
    assert not (tmp_path/".work"/"MOTOR-310-TEST").exists()

def test_append_rejects_sequence_gap(tmp_path):
    session=RawLogV2Writer(tmp_path).begin(manifest_fields())
    bad=session_event(); bad["record_seq"]=2
    with pytest.raises(ValueError,match="continuous"): session.append(bad)



def test_crash_recovery_materializes_acknowledged_inflight_stage_as_interrupted(tmp_path):
    writer = RawLogV2Writer(tmp_path)
    fields = manifest_fields()
    session = writer.begin(fields)
    context = "context-pwm-12"
    session.append({
        "schema_version": "2.0.0", "record_type": "SESSION_EVENT",
        "record_id": "ack-pwm-12", "record_seq": 1,
        "log_id": fields["log_id"], "measurement_session_id": fields["measurement_session_id"],
        "recorded_at_utc": "2026-11-01T00:00:12.010Z",
        "event": "OTHER", "host_monotonic_ns": 12_010_000_000,
        "details": {"kind": "PWM_ACK_RECEIVED", "stage_index": 12,
                    "stage_id": "PWM-12", "stage_context_id": context,
                    "ack_received_at_utc": "2026-11-01T00:00:12.010Z",
                    "ack_received_host_monotonic_ns": 12_010_000_000},
    })
    session.append({
        "schema_version": "2.0.0", "record_type": "ADC_SAMPLE",
        "record_id": "sample-record-12", "record_seq": 2,
        "log_id": fields["log_id"], "measurement_session_id": fields["measurement_session_id"],
        "recorded_at_utc": "2026-11-01T00:00:12.100Z", "sample_id": "sample-12",
        "channel": "A0", "sensor": "ACS712 #1", "signal_role": "winding_current",
        "adc_raw": 512, "adc_resolution_bits": 10, "raw_unit": "count",
        "device_timestamp_us_u32": 10, "device_timestamp_point": "conversion_midpoint",
        "device_epoch_id": "boot-1", "device_elapsed_us": 10, "device_sample_sequence": 1,
        "host_received_at_utc": "2026-11-01T00:00:12.100Z",
        "host_received_monotonic_ns": 12_100_000_000,
        "stage_context_id": context, "stage_id": "PWM-12",
        "stage_assignment": "confirmed", "calibration_id": None,
        "validity": "valid", "invalid_reason": None,
    })
    original = (tmp_path / ".work" / fields["log_id"] / "records.jsonl").read_bytes()
    recovery = writer.recover_incomplete(fields["log_id"], recovered_at_utc="2026-11-01T00:00:20.000Z")
    original_copy = (tmp_path / ".recovery" / fields["log_id"] /
                     recovery["recovery_id"] / "original" / "records.jsonl")
    assert original_copy.read_bytes() == original
    assert len(recovery["recovered_stage_records"]) == 1
    assert recovery["recovered_stage_records"][0]["stage_index"] == 12
    assert recovery["recovered_stage_records"][0]["stage_status"] == "aborted"

    final = tmp_path / fields["log_id"]
    manifest = json.loads((final / "manifest.json").read_text())
    records = [json.loads(line) for line in (final / "records.jsonl").read_text().splitlines()]
    recovered_stage = next(r for r in records if r.get("record_type") == "PWM_STAGE")
    assert recovered_stage["stage_status"] == "aborted"
    assert recovered_stage["termination_reason"] == "process_interrupted"
    assert recovered_stage["output_state"] == "unknown"
    assert recovered_stage["pwm_command_sent_at_utc"] is None
    assert recovered_stage["end_host_monotonic_ns"] is None
    assert recovered_stage["actual_duration_ms"] is None
    assert validate_package(manifest, records, raise_on_error=False) == []


def test_crash_recovery_marks_disarm_acknowledged_stage_completed(tmp_path):
    writer = RawLogV2Writer(tmp_path)
    fields = manifest_fields()
    session = writer.begin(fields)
    context = "context-pwm-03"
    session.append({
        "schema_version": "2.0.0", "record_type": "SESSION_EVENT",
        "record_id": "sent-pwm-03", "record_seq": 1,
        "log_id": fields["log_id"], "measurement_session_id": fields["measurement_session_id"],
        "recorded_at_utc": "2026-11-01T00:00:03.000Z", "event": "OTHER",
        "host_monotonic_ns": 3_000_000_000,
        "details": {"kind": "PWM_COMMAND_SENT", "stage_index": 3, "stage_id": "PWM-03",
                    "stage_context_id": context, "command_sent_at_utc": "2026-11-01T00:00:03.000Z"},
    })
    session.append({
        "schema_version": "2.0.0", "record_type": "SESSION_EVENT",
        "record_id": "ack-pwm-03", "record_seq": 2,
        "log_id": fields["log_id"], "measurement_session_id": fields["measurement_session_id"],
        "recorded_at_utc": "2026-11-01T00:00:03.010Z", "event": "OTHER",
        "host_monotonic_ns": 3_010_000_000,
        "details": {"kind": "PWM_ACK_RECEIVED", "stage_index": 3, "stage_id": "PWM-03",
                    "stage_context_id": context, "command_sent_at_utc": "2026-11-01T00:00:03.000Z",
                    "ack_received_at_utc": "2026-11-01T00:00:03.010Z",
                    "ack_received_host_monotonic_ns": 3_010_000_000},
    })
    session.append({
        "schema_version": "2.0.0", "record_type": "SESSION_EVENT",
        "record_id": "disarm-pwm-03", "record_seq": 3,
        "log_id": fields["log_id"], "measurement_session_id": fields["measurement_session_id"],
        "recorded_at_utc": "2026-11-01T00:00:13.020Z", "event": "OTHER",
        "host_monotonic_ns": 13_010_000_000,
        "details": {"kind": "STAGE_DISARM_ACKNOWLEDGED", "stage_index": 3,
                    "stage_id": "PWM-03", "stage_context_id": context,
                    "stage_ended_at_utc": "2026-11-01T00:00:13.000Z",
                    "stage_end_host_monotonic_ns": 13_010_000_000},
    })
    recovery = writer.recover_incomplete(fields["log_id"], recovered_at_utc="2026-11-01T00:00:14.000Z")
    assert recovery["recovered_stage_records"][0]["stage_status"] == "completed"
    final = tmp_path / fields["log_id"]
    manifest = json.loads((final / "manifest.json").read_text())
    records = [json.loads(line) for line in (final / "records.jsonl").read_text().splitlines()]
    assert validate_package(manifest, records, raise_on_error=False) == []


def test_crash_recovery_preserves_original_and_drops_partial_tail(tmp_path):
    writer=RawLogV2Writer(tmp_path); session=writer.begin(manifest_fields()); session.append(session_event())
    work=tmp_path/".work"/"MOTOR-310-TEST"; rp=work/"records.jsonl"
    partial=b'{"schema_version":"2.0.0","record_type":"PWM_STAGE"'
    with rp.open("ab") as f: f.write(partial); f.flush()
    original_records=rp.read_bytes(); original_state=(work/"work_state.json").read_bytes()
    recovery=writer.recover_incomplete("MOTOR-310-TEST",recovered_at_utc=NOW)
    recovery_dir=tmp_path/".recovery"/"MOTOR-310-TEST"/recovery["recovery_id"]/"original"
    assert (recovery_dir/"records.jsonl").read_bytes()==original_records
    assert (recovery_dir/"work_state.json").read_bytes()==original_state
    assert recovery["incomplete_tail_present"] and recovery["incomplete_tail_size_bytes"]==len(partial)
    final=tmp_path/"MOTOR-310-TEST"
    assert sorted(p.name for p in final.iterdir())==["manifest.json","records.jsonl"]
    recovered=(final/"records.jsonl").read_bytes()
    assert recovered.endswith(b"\n") and partial not in recovered and b"PWM_STAGE" not in recovered
    manifest=json.loads((final/"manifest.json").read_text())
    assert manifest["status"]=="incomplete" and manifest["record_counts"]=={"SESSION_EVENT":1}
    assert not work.exists()

def test_recovery_is_idempotent_and_does_not_overwrite_final_package(tmp_path):
    writer=RawLogV2Writer(tmp_path); session=writer.begin(manifest_fields()); session.append(session_event())
    first=writer.recover_incomplete("MOTOR-310-TEST",recovered_at_utc=NOW)
    final=tmp_path/"MOTOR-310-TEST"; before_m=(final/"manifest.json").read_bytes(); before_r=(final/"records.jsonl").read_bytes()
    second=writer.recover_incomplete("MOTOR-310-TEST",recovered_at_utc=NOW)
    assert second["recovery_id"]==first["recovery_id"]
    assert (final/"manifest.json").read_bytes()==before_m and (final/"records.jsonl").read_bytes()==before_r
    with pytest.raises(ExistingPackageError): writer.begin(manifest_fields())

def test_recovery_source_is_kept_if_final_package_conflicts(tmp_path):
    writer=RawLogV2Writer(tmp_path); session=writer.begin(manifest_fields()); session.append(session_event())
    final=tmp_path/"MOTOR-310-TEST"; final.mkdir(); (final/"records.jsonl").write_text("foreign\n")
    with pytest.raises(ExistingPackageError): writer.recover_incomplete("MOTOR-310-TEST",recovered_at_utc=NOW)
    assert (tmp_path/".work"/"MOTOR-310-TEST"/"records.jsonl").exists()
    assert list((tmp_path/".recovery"/"MOTOR-310-TEST").glob("crash-*/original/records.jsonl"))

def test_v1_payload_is_not_accepted_as_v2():
    errors=validate_package({"schema_version":"1"},[],raise_on_error=False)
    assert any("schema_name" in e for e in errors) and any("schema_version" in e for e in errors)

def test_a1_cannot_be_relabelled_or_converted():
    from raw_log_v2.validator import validate_record
    manifest=manifest_fields()
    sample={"schema_version":"2.0.0","record_type":"ADC_SAMPLE","record_id":"a1","record_seq":1,
      "log_id":manifest["log_id"],"measurement_session_id":manifest["measurement_session_id"],
      "recorded_at_utc":NOW,"sample_id":"sample-a1","channel":"A1","sensor":"ACS712 #2",
      "signal_role":"winding_current","adc_raw":512,"adc_resolution_bits":10,"raw_unit":"count",
      "device_timestamp_us_u32":1,"device_timestamp_point":"conversion_midpoint","device_epoch_id":"boot-1",
      "device_elapsed_us":1,"device_sample_sequence":1,"host_received_at_utc":NOW,
      "host_received_monotonic_ns":1,"stage_context_id":None,"stage_id":None,
      "stage_assignment":"unresolved","calibration_id":None,"validity":"valid","invalid_reason":None,
      "converted_value":0.5,"converted_unit":"A"}
    errors=validate_record(sample,manifest)
    assert any("sensor/signal_role" in e for e in errors) and any("A1 conversion" in e for e in errors)

def test_raw_only_calibration_cannot_be_referenced():
    manifest=manifest_fields()
    roles={"A0":("winding_current","winding_current_zero_reference"),
           "A1":("brush_stability_observation","brush_observation_reference"),
           "A4":("voltage_v4","voltage_input_reference"),"A5":("voltage_v5","voltage_input_reference")}
    channels={k:{"signal_role":v[0],"calibration_role":v[1],"parameter_status":"raw_only_unparsed","parameters":None} for k,v in roles.items()}
    cal={"schema_version":"2.0.0","record_type":"CALIBRATION","record_id":"cal-record","record_seq":1,
      "log_id":manifest["log_id"],"measurement_session_id":manifest["measurement_session_id"],
      "recorded_at_utc":NOW,"calibration_id":"cal-raw","source":"firmware_CAL_line","raw_line":"CAL,raw",
      "captured_at_utc":NOW,"captured_host_monotonic_ns":1,"effective_from_event_id":None,
      "effective_until_event_id":None,"application_status":"raw_capture_only","channels":channels}
    sample={"schema_version":"2.0.0","record_type":"ADC_SAMPLE","record_id":"sample-record","record_seq":2,
      "log_id":manifest["log_id"],"measurement_session_id":manifest["measurement_session_id"],
      "recorded_at_utc":NOW,"sample_id":"sample-a0","channel":"A0","sensor":"ACS712 #1",
      "signal_role":"winding_current","adc_raw":512,"adc_resolution_bits":10,"raw_unit":"count",
      "device_timestamp_us_u32":2,"device_timestamp_point":"conversion_midpoint","device_epoch_id":"boot-1",
      "device_elapsed_us":2,"device_sample_sequence":2,"host_received_at_utc":NOW,
      "host_received_monotonic_ns":2,"stage_context_id":None,"stage_id":None,
      "stage_assignment":"unresolved","calibration_id":"cal-raw","validity":"valid","invalid_reason":None}
    manifest["record_counts"]={"CALIBRATION":1,"ADC_SAMPLE":1}
    errors=validate_package(manifest,[cal,sample],raise_on_error=False)
    assert any("non-applicable raw-only" in e for e in errors)


def test_crash_after_manifest_commit_keeps_committed_package(tmp_path, monkeypatch):
    import raw_log_v2.storage as storage
    writer=RawLogV2Writer(tmp_path); session=writer.begin(manifest_fields())
    for i in range(31): session.append(stage_record(i))
    original=storage._atomic_replace_json
    calls={"count":0}
    def fail_after_manifest(path, value):
        calls["count"] += 1
        if calls["count"] == 2:
            raise OSError("simulated process crash after manifest publication")
        return original(path, value)
    monkeypatch.setattr(storage, "_atomic_replace_json", fail_after_manifest)
    with pytest.raises(OSError, match="simulated process crash"):
        session.finalize({"ended_at_utc":NOW}, "completed", NOW)
    # The manifest is the commit point; recovery must not downgrade it to incomplete.
    recovery=writer.recover_incomplete("MOTOR-310-TEST", recovered_at_utc=NOW)
    assert recovery["recovery_status"] == "already_published"
    final=tmp_path/"MOTOR-310-TEST"
    assert json.loads((final/"manifest.json").read_text())["status"] == "completed"
    assert sorted(p.name for p in final.iterdir()) == ["manifest.json", "records.jsonl"]
    assert not (tmp_path/".work"/"MOTOR-310-TEST").exists()


def test_validator_reports_record_count_and_sequence_mismatch():
    manifest=manifest_fields()
    record=session_event()
    manifest.update({"created_at_utc":NOW,"ended_at_utc":None,"status":"incomplete",
        "planned_stage_count":31,"planned_stage_duration_ms":10000,"planned_total_duration_ms":310000,
        "record_counts":{"SESSION_EVENT":2}})
    record["record_seq"]=2
    errors=validate_package(manifest,[record],raise_on_error=False)
    assert any("record_counts mismatch" in error for error in errors)
    assert any("record_seq" in error for error in errors)


def test_incomplete_package_does_not_require_or_invent_missing_stages():
    manifest=manifest_fields()
    record=session_event()
    manifest.update({"created_at_utc":NOW,"ended_at_utc":None,"status":"incomplete",
        "planned_stage_count":31,"planned_stage_duration_ms":10000,"planned_total_duration_ms":310000,
        "record_counts":{"SESSION_EVENT":1}})
    assert validate_package(manifest,[record],raise_on_error=False) == []


def test_validator_does_not_crash_on_wrong_json_value_types():
    manifest=manifest_fields()
    record=session_event()
    record["record_type"]=[]
    errors=validate_package(manifest,[record],raise_on_error=False)
    assert any("record_type" in error for error in errors)


def test_final_package_rejects_unexpected_files_without_deleting_work(tmp_path):
    writer=RawLogV2Writer(tmp_path)
    session=writer.begin(manifest_fields())
    session.append(session_event())
    final=tmp_path/"MOTOR-310-TEST"
    final.mkdir()
    (final/"unexpected.bin").write_bytes(b"foreign")
    with pytest.raises(ExistingPackageError, match="unexpected entry"):
        writer.recover_incomplete("MOTOR-310-TEST", recovered_at_utc=NOW)
    assert (tmp_path/".work"/"MOTOR-310-TEST"/"records.jsonl").exists()
    assert (final/"unexpected.bin").read_bytes()==b"foreign"


def test_confirmed_adc_sample_must_match_stage_context():
    manifest=manifest_fields()
    stage=stage_record(0)
    sample={"schema_version":"2.0.0","record_type":"ADC_SAMPLE","record_id":"sample-record",
        "record_seq":2,"log_id":manifest["log_id"],"measurement_session_id":manifest["measurement_session_id"],
        "recorded_at_utc":"2026-11-01T00:01:00.000Z","sample_id":"sample-a0","channel":"A0",
        "sensor":"ACS712 #1","signal_role":"winding_current","adc_raw":512,
        "adc_resolution_bits":10,"raw_unit":"count","device_timestamp_us_u32":10,
        "device_timestamp_point":"conversion_midpoint","device_epoch_id":"boot-1",
        "device_elapsed_us":10,"device_sample_sequence":1,"host_received_at_utc":"2026-11-01T00:01:00.000Z",
        "host_received_monotonic_ns":10,"stage_context_id":"wrong-context","stage_id":"PWM-00",
        "stage_assignment":"confirmed","calibration_id":None,"validity":"valid","invalid_reason":None}
    manifest.update({"created_at_utc":NOW,"ended_at_utc":None,"status":"incomplete",
        "planned_stage_count":31,"planned_stage_duration_ms":10000,"planned_total_duration_ms":310000,
        "record_counts":{"PWM_STAGE":1,"ADC_SAMPLE":1}})
    errors=validate_package(manifest,[stage,sample],raise_on_error=False)
    assert any("confirmed context has no PWM_STAGE" in error for error in errors)


def test_duplicate_record_ids_are_rejected():
    manifest=manifest_fields()
    first=session_event()
    second=session_event()
    second["record_seq"]=2
    manifest.update({"created_at_utc":NOW,"ended_at_utc":None,"status":"incomplete",
        "planned_stage_count":31,"planned_stage_duration_ms":10000,"planned_total_duration_ms":310000,
        "record_counts":{"SESSION_EVENT":2}})
    errors=validate_package(manifest,[first,second],raise_on_error=False)
    assert any("duplicate record_id" in error for error in errors)


def test_controlled_abort_has_completed_aborted_then_not_reached_stages():
    manifest=manifest_fields()
    records=[]
    for index in range(31):
        if index == 0:
            record=stage_record(0)
            record.update({"started_at_utc":"2026-11-01T00:00:00.010Z",
                "ended_at_utc":"2026-11-01T00:00:10.010Z",
                "start_host_monotonic_ns":5010000000,"end_host_monotonic_ns":15010000000,
                "actual_duration_ms":10000,"pwm_command_sent_at_utc":"2026-11-01T00:00:00.000Z",
                "pwm_applied_ack_received_at_utc":"2026-11-01T00:00:00.010Z",
                "recorded_at_utc":"2026-11-01T00:00:10.031Z"})
        elif index == 1:
            record=stage_record(1)
            record.update({"stage_status":"aborted","started_at_utc":"2026-11-01T00:00:10.030Z",
                "ended_at_utc":"2026-11-01T00:00:13.500Z",
                "start_host_monotonic_ns":15030000000,"end_host_monotonic_ns":18500000000,
                "actual_duration_ms":3470,"pwm_command_sent_at_utc":"2026-11-01T00:00:10.010Z",
                "pwm_applied_ack_received_at_utc":"2026-11-01T00:00:10.030Z",
                "recorded_at_utc":"2026-11-01T00:00:13.500Z","termination_reason":"user_stop"})
        else:
            record=stage_record(index)
            record.update({"stage_status":"not_reached","started_at_utc":None,"ended_at_utc":None,
                "start_host_monotonic_ns":None,"end_host_monotonic_ns":None,"actual_duration_ms":None,
                "pwm_command_sent_at_utc":None,"pwm_applied_ack_received_at_utc":None,
                "output_state":"unknown","stage_context_id":None,
                "termination_reason":"not_started_after_abort",
                "recorded_at_utc":"2026-11-01T00:00:13.600Z"})
        record["record_seq"]=index+1
        records.append(record)
    manifest.update({"created_at_utc":"2026-11-01T00:00:13.700Z",
        "started_at_utc":"2026-11-01T00:00:00.000Z",
        "ended_at_utc":"2026-11-01T00:00:13.600Z","status":"aborted",
        "planned_stage_count":31,"planned_stage_duration_ms":10000,
        "planned_total_duration_ms":310000,"record_counts":{"PWM_STAGE":31}})
    assert validate_package(manifest,records,raise_on_error=False) == []


def test_recovery_resumes_after_partial_original_and_package_staging(tmp_path, monkeypatch):
    import raw_log_v2.storage as storage
    writer=RawLogV2Writer(tmp_path)
    session=writer.begin(manifest_fields())
    session.append(session_event())
    work=tmp_path/".work"/"MOTOR-310-TEST"
    original_records=(work/"records.jsonl").read_bytes()
    original_state=(work/"work_state.json").read_bytes()
    real_write=storage._write_new_file
    failures={"preserve":0,"records":0}

    def fail_once(path,payload):
        if path.name.startswith(".preserve-") and failures["preserve"] == 0:
            failures["preserve"] += 1
            real_write(path,b"partial-original-copy")
            raise OSError("simulated crash during original staging")
        if path.name.startswith(".records-") and failures["records"] == 0:
            failures["records"] += 1
            real_write(path,b"partial-final-records")
            raise OSError("simulated crash during final records staging")
        return real_write(path,payload)

    monkeypatch.setattr(storage,"_write_new_file",fail_once)
    with pytest.raises(OSError,match="original staging"):
        writer.recover_incomplete("MOTOR-310-TEST",recovered_at_utc=NOW)
    assert (work/"records.jsonl").read_bytes()==original_records
    with pytest.raises(OSError,match="final records staging"):
        writer.recover_incomplete("MOTOR-310-TEST",recovered_at_utc=NOW)

    recovery_dirs=list((tmp_path/".recovery"/"MOTOR-310-TEST").glob("crash-*"))
    assert len(recovery_dirs)==1
    original_dir=recovery_dirs[0]/"original"
    assert (original_dir/"records.jsonl").read_bytes()==original_records
    assert (original_dir/"work_state.json").read_bytes()==original_state
    assert (work/"records.jsonl").read_bytes()==original_records

    monkeypatch.setattr(storage,"_write_new_file",real_write)
    recovery=writer.recover_incomplete("MOTOR-310-TEST",recovered_at_utc=NOW)
    final=tmp_path/"MOTOR-310-TEST"
    assert recovery["recovery_id"]==recovery_dirs[0].name
    assert sorted(p.name for p in final.iterdir())==["manifest.json","records.jsonl"]
    assert (final/"records.jsonl").read_bytes()==original_records
    assert json.loads((final/"manifest.json").read_text())["status"]=="incomplete"
    assert not work.exists()


def test_startup_discovery_recovers_all_pending_work_in_stable_order(tmp_path):
    writer=RawLogV2Writer(tmp_path)
    assert writer.list_incomplete_work()==[]
    writer.begin(manifest_fields("MOTOR-Z"))
    writer.begin(manifest_fields("MOTOR-A"))
    assert writer.list_incomplete_work()==["MOTOR-A","MOTOR-Z"]
    results=writer.recover_pending()
    assert [item["log_id"] for item in results]==["MOTOR-A","MOTOR-Z"]
    assert writer.list_incomplete_work()==[]
    for log_id in ("MOTOR-A","MOTOR-Z"):
        manifest=json.loads((tmp_path/log_id/"manifest.json").read_text())
        assert manifest["status"]=="incomplete"
        assert manifest["record_counts"]=={}


def test_publish_existing_identical_file_reconfirms_parent_directory_fsync(tmp_path, monkeypatch):
    import raw_log_v2.storage as storage
    target=tmp_path/"package"/"manifest.json"
    target.parent.mkdir()
    target.write_bytes(b'{"status":"incomplete"}\\n')
    real_fsync=storage._fsync_dir
    calls=[]
    monkeypatch.setattr(storage,"_fsync_dir",lambda path:(calls.append(Path(path)),real_fsync(path))[1])
    storage._publish_new_file(target,b'{"status":"incomplete"}\\n',tmp_path/"package"/".manifest.tmp")
    assert calls==[target.parent]


def test_retry_after_manifest_link_fsync_failure_syncs_recovery_and_final_before_work_delete(tmp_path, monkeypatch):
    import raw_log_v2.storage as storage
    writer=RawLogV2Writer(tmp_path)
    session=writer.begin(manifest_fields())
    session.append(session_event())
    work=tmp_path/".work"/"MOTOR-310-TEST"
    real_fsync=storage._fsync_dir
    real_rmtree=storage.shutil.rmtree
    synced=[]
    fail={"once":True}
    delete_observation=[]

    def injected_fsync(path):
        path=Path(path)
        if (fail["once"] and path==tmp_path/"MOTOR-310-TEST"
                and (path/"manifest.json").is_file()):
            fail["once"]=False
            raise storage.DurabilityError("simulated crash after manifest hard-link before parent fsync")
        result=real_fsync(path)
        synced.append(path)
        return result

    def observed_rmtree(path,*args,**kwargs):
        if Path(path)==work:
            delete_observation.append(list(synced))
        return real_rmtree(path,*args,**kwargs)

    monkeypatch.setattr(storage,"_fsync_dir",injected_fsync)
    monkeypatch.setattr(storage.shutil,"rmtree",observed_rmtree)
    with pytest.raises(storage.DurabilityError,match="after manifest hard-link"):
        writer.recover_incomplete("MOTOR-310-TEST",recovered_at_utc=NOW)
    assert work.is_dir(),".work must remain after failed manifest directory fsync"

    recovery_dir=next((tmp_path/".recovery"/"MOTOR-310-TEST").glob("crash-*"))
    original_dir=recovery_dir/"original"
    synced.clear()
    result=writer.recover_incomplete("MOTOR-310-TEST",recovered_at_utc=NOW)

    assert result["recovery_id"]==recovery_dir.name
    assert not work.exists()
    assert len(delete_observation)==1
    syncs_before_delete=delete_observation[0]
    assert original_dir in syncs_before_delete
    assert recovery_dir in syncs_before_delete
    assert recovery_dir.parent in syncs_before_delete
    assert tmp_path/".recovery" in syncs_before_delete
    assert tmp_path/"MOTOR-310-TEST" in syncs_before_delete
    assert syncs_before_delete.index(original_dir) < syncs_before_delete.index(tmp_path/"MOTOR-310-TEST")
    assert json.loads((tmp_path/"MOTOR-310-TEST"/"manifest.json").read_text())["status"]=="incomplete"


def test_retry_after_recovery_original_link_fsync_failure_preserves_work_until_resynced(tmp_path, monkeypatch):
    import raw_log_v2.storage as storage
    writer=RawLogV2Writer(tmp_path)
    session=writer.begin(manifest_fields())
    session.append(session_event())
    work=tmp_path/".work"/"MOTOR-310-TEST"
    original_records=(work/"records.jsonl").read_bytes()
    real_fsync=storage._fsync_dir
    real_rmtree=storage.shutil.rmtree
    synced=[]
    fail={"once":True}
    delete_observation=[]

    def injected_fsync(path):
        path=Path(path)
        if fail["once"] and path.name=="original" and path.parent.name.startswith("crash-"):
            fail["once"]=False
            raise storage.DurabilityError("simulated crash after recovery-original hard-link")
        result=real_fsync(path)
        synced.append(path)
        return result

    def observed_rmtree(path,*args,**kwargs):
        if Path(path)==work:
            delete_observation.append(list(synced))
        return real_rmtree(path,*args,**kwargs)

    monkeypatch.setattr(storage,"_fsync_dir",injected_fsync)
    monkeypatch.setattr(storage.shutil,"rmtree",observed_rmtree)
    with pytest.raises(storage.DurabilityError,match="recovery-original hard-link"):
        writer.recover_incomplete("MOTOR-310-TEST",recovered_at_utc=NOW)
    assert work.is_dir()
    recovery_dir=next((tmp_path/".recovery"/"MOTOR-310-TEST").glob("crash-*"))
    original_dir=recovery_dir/"original"
    assert (original_dir/"records.jsonl").read_bytes()==original_records

    synced.clear()
    result=writer.recover_incomplete("MOTOR-310-TEST",recovered_at_utc=NOW)
    assert result["recovery_id"]==recovery_dir.name
    assert not work.exists()
    assert len(delete_observation)==1
    assert original_dir in delete_observation[0]
    assert recovery_dir in delete_observation[0]
    assert recovery_dir.parent in delete_observation[0]


def test_normal_finalize_manifest_link_fsync_failure_is_reconfirmed_before_work_delete(tmp_path, monkeypatch):
    import raw_log_v2.storage as storage
    writer=RawLogV2Writer(tmp_path)
    session=writer.begin(manifest_fields())
    for i in range(31): session.append(stage_record(i))
    work=tmp_path/".work"/"MOTOR-310-TEST"
    final=tmp_path/"MOTOR-310-TEST"
    real_fsync=storage._fsync_dir
    real_rmtree=storage.shutil.rmtree
    failures={"remaining":2}
    synced=[]
    delete_observation=[]

    def injected_fsync(path):
        path=Path(path)
        if path==final and (final/"manifest.json").is_file() and failures["remaining"]:
            failures["remaining"]-=1
            raise storage.DurabilityError("simulated normal-finalize manifest directory fsync failure")
        result=real_fsync(path)
        synced.append(path)
        return result

    def observed_rmtree(path,*args,**kwargs):
        if Path(path)==work:
            delete_observation.append(list(synced))
        return real_rmtree(path,*args,**kwargs)

    monkeypatch.setattr(storage,"_fsync_dir",injected_fsync)
    monkeypatch.setattr(storage.shutil,"rmtree",observed_rmtree)

    # Failure immediately after manifest hard-link in normal finalize.
    with pytest.raises(storage.DurabilityError,match="normal-finalize manifest"):
        session.finalize({"ended_at_utc":END},"completed",END)
    assert work.is_dir(),".work must remain after finalize directory-fsync failure"
    assert (final/"manifest.json").is_file()

    # First startup-recovery attempt also fails its final-directory durability check.
    with pytest.raises(storage.DurabilityError,match="normal-finalize manifest"):
        writer.recover_incomplete("MOTOR-310-TEST",recovered_at_utc=NOW)
    assert work.is_dir(),".work must remain when startup recovery fsync fails"
    assert delete_observation==[]

    # A later retry must fsync final_dir successfully before removing .work.
    synced.clear()
    result=writer.recover_pending()
    assert result[0]["recovery_status"]=="already_published"
    assert not work.exists()
    assert len(delete_observation)==1
    assert final in delete_observation[0]
    assert failures["remaining"]==0
    assert sorted(p.name for p in final.iterdir())==["manifest.json","records.jsonl"]
    assert json.loads((final/"manifest.json").read_text())["status"]=="completed"
