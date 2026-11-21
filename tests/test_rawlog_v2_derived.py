from communication.rawlog_v2_analysis import ChannelValue, WindingResistanceResult
from communication.rawlog_v2_derived import (
    aggregate_winding_resistance,
    summarize_a1_brush_signal,
    winding_result_to_derived,
)


def point(sequence, value, valid=True, ids=None, reason=None):
    return WindingResistanceResult(
        session_id="s1", sequence=sequence, valid=valid,
        resistance_ohm=value if valid else None,
        voltage_delta_v=1.0 if valid else None,
        current_a=0.1 if valid else None,
        a4_a5_skew_us=1, a0_to_voltage_skew_us=1,
        input_sample_ids=tuple(ids or (f"s1:{sequence}:A0", f"s1:{sequence}:A4", f"s1:{sequence}:A5")),
        invalid_reason=None if valid else (reason or "invalid point"),
    )


def test_point_result_adapts_to_derived_storage_contract():
    result = winding_result_to_derived(point(1, 10.0))
    assert result["metric"] == "winding_resistance_point"
    assert result["value"] == 10.0
    assert result["valid"] is True
    assert result["input_sample_ids"] == ["s1:1:A0", "s1:1:A4", "s1:1:A5"]


def test_invalid_point_keeps_reason_and_null_value():
    result = winding_result_to_derived(point(1, None, valid=False, reason="zero current"))
    assert result["value"] is None
    assert result["valid"] is False
    assert result["invalid_reason"] == "zero current"


def test_a1_descriptive_statistics_are_independent_and_not_a_score():
    samples = [
        ChannelValue("A1", "s1:1:A1", 2.0, "A", 100),
        ChannelValue("A1", "s1:2:A1", 4.0, "A", 200),
        ChannelValue("A1", "s1:3:A1", 6.0, "A", 300),
    ]
    rows = summarize_a1_brush_signal(samples)
    by_metric = {row["metric"]: row for row in rows}
    assert by_metric["a1_mean"]["value"] == 4.0
    assert by_metric["a1_min"]["value"] == 2.0
    assert by_metric["a1_max"]["value"] == 6.0
    assert by_metric["a1_range"]["value"] == 4.0
    assert all(row["input_sample_ids"] == [item.sample_id for item in samples] for row in rows)
    assert all("stability_score" not in row["metric"] for row in rows)


def test_a1_statistics_reject_mixed_channels_and_units():
    import pytest
    with pytest.raises(ValueError, match="A1 samples only"):
        summarize_a1_brush_signal([ChannelValue("A0", "s1:1:A0", 1.0, "A", 1)])
    with pytest.raises(ValueError, match="one consistent unit"):
        summarize_a1_brush_signal([
            ChannelValue("A1", "s1:1:A1", 1.0, "A", 1),
            ChannelValue("A1", "s1:2:A1", 2.0, "V", 2),
        ])


def test_multi_sample_resistance_uses_median_and_explicit_count():
    result = aggregate_winding_resistance(
        [point(1, 9.0), point(2, 10.0), point(3, 100.0)],
        minimum_valid_samples=3,
    )
    assert result["valid"] is True
    assert result["value"] == 10.0
    assert result["metric"] == "winding_resistance_median"
    assert len(result["input_sample_ids"]) == 9


def test_multi_sample_policy_invalidates_insufficient_or_excess_spread():
    insufficient = aggregate_winding_resistance(
        [point(1, 10.0), point(2, None, valid=False)],
        minimum_valid_samples=2,
    )
    assert insufficient["valid"] is False
    assert "insufficient valid samples" in insufficient["invalid_reason"]

    spread = aggregate_winding_resistance(
        [point(1, 10.0), point(2, 12.0)],
        minimum_valid_samples=2,
        maximum_range_ohm=1.0,
    )
    assert spread["valid"] is False
    assert "exceeds configured maximum" in spread["invalid_reason"]
