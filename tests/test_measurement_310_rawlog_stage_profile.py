import pytest

from measurement_310.rawlog_stage_profile import (
    BATCH_SAMPLES,
    CHANNEL_CODE_ORDER,
    MIN_SAMPLES,
    percentile,
    summarize,
    run_profile,
)


def test_profile_declares_protocol_v2_channel_order_without_claiming_device_timing():
    assert BATCH_SAMPLES == 12
    assert CHANNEL_CODE_ORDER == (0, 1, 4, 5, 2, 3) * 2
    assert MIN_SAMPLES == 10_000


def test_nearest_rank_percentile_matches_profile_convention():
    values = [10, 20, 30, 40, 50]
    assert percentile(values, 0.50) == 30
    assert percentile(values, 0.95) == 50
    assert percentile(values, 1.0) == 50


def test_summary_reports_all_required_distribution_fields():
    result = summarize([10, 20, 30, 40, 50])
    assert result == {
        "count": 5,
        "mean_ns": 30,
        "p50_ns": 30,
        "p95_ns": 50,
        "p99_ns": 50,
        "p999_ns": 50,
        "max_ns": 50,
    }


@pytest.mark.parametrize("samples", [0, 9996, 9999])
def test_profile_rejects_fewer_than_10000_commits_before_storage_access(tmp_path, samples):
    with pytest.raises(ValueError, match="at least 10,000"):
        run_profile(tmp_path, samples)


def test_profile_rejects_partial_adc_batch_count(tmp_path):
    with pytest.raises(ValueError, match="multiple of 12"):
        run_profile(tmp_path, 10000)
