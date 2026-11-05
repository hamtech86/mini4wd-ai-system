import pytest

from measurement_310.fsync_profile import nearest_rank, percentile_summary


def test_nearest_rank_uses_ceiling_rank():
    assert nearest_rank([9, 1, 5, 3], 0.50) == 3
    assert nearest_rank(list(range(1, 1001)), 0.999) == 999


def test_nearest_rank_rejects_invalid_arguments():
    with pytest.raises(ValueError):
        nearest_rank([], 0.5)
    with pytest.raises(ValueError):
        nearest_rank([1, 2], 0)
    with pytest.raises(ValueError):
        nearest_rank([1, 2], 1.1)


def test_percentile_summary_reports_count_and_max():
    summary = percentile_summary([5, 1, 4, 2, 3])
    assert summary["count"] == 5
    assert summary["p50_ns"] == 3
    assert summary["max_ns"] == 5


def test_t18_rejects_underqualified_sample_and_timing_budgets(tmp_path):
    from measurement_310.fsync_profile import run_profile

    with pytest.raises(ValueError, match="10,000 samples"):
        run_profile(tmp_path / "too-few", 9999, 10000, 1000, 1000)
    with pytest.raises(ValueError, match="stage budget is fixed"):
        run_profile(tmp_path / "wrong-stage", 10000, 9999, 1000, 1000)
    with pytest.raises(ValueError, match="STOP reserve must be at least"):
        run_profile(tmp_path / "zero-stop", 10000, 10000, 0, 1000)
    with pytest.raises(ValueError, match="additional margin must be at least"):
        run_profile(tmp_path / "zero-margin", 10000, 10000, 1000, 0)


def test_t18_cli_defaults_use_adopted_reserve_and_margin(monkeypatch, tmp_path):
    import measurement_310.fsync_profile as profile

    captured = {}
    def fake_run(output_dir, samples, stage_ms, stop_reserve_ms, margin_ms):
        captured.update(samples=samples, stage_ms=stage_ms,
                        stop_reserve_ms=stop_reserve_ms, margin_ms=margin_ms)
        return {"budget": {"profile_within_budget": True}}

    monkeypatch.setattr(profile, "run_profile", fake_run)
    assert profile.main(["--output-dir", str(tmp_path)]) == 0
    assert captured == {
        "samples": 10000, "stage_ms": 10000,
        "stop_reserve_ms": 1000, "margin_ms": 1000,
    }
