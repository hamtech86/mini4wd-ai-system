from measurement_310.t18_production_profile import run_profile


def test_full_production_path_profile_runs_all_31_stages_and_verifies_artifacts(tmp_path):
    report = run_profile(tmp_path / "t18-profile")
    assert report["stage_count"] == 31
    assert report["adc_batches"] == 3100
    assert report["adc_slots"] == 37200
    assert report["adc_sample_records"] == 37200
    assert report["pwm_stage_records"] == 31
    assert report["loss_window_summary_count"] == 310
    assert report["loss_windows_all_pass"] is True
    assert report["rawlog_validation_errors"] == []
    assert report["evidence_bundle_verified"] is True
    assert report["normal_completion_stop_request_count"] == 1
