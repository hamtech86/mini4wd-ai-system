import json
import pytest
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
