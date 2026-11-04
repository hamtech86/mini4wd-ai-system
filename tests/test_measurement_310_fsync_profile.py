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
