import pytest

from communication.rawlog_v2_alignment import AuxAlignmentError, align_aux_records
from communication.rawlog_v2_aux import parse_aux_line


def parse(sequence, channel, timestamp, *, session="session_1", phase="WINDING", direction="FWD"):
    return parse_aux_line(
        f"AUX,2,{session},{sequence},{phase},{direction},0,MEASURE,{channel},512,{timestamp}"
    )


def test_aligns_a0_a4_a5_and_reports_actual_signed_skew_without_threshold():
    records = [
        parse(10, "A0", 100),
        parse(10, "A4", 107),
        parse(10, "A5", 119),
        parse(11, "A1", 130, phase="BRUSH"),
    ]

    cycles = align_aux_records(records)

    assert len(cycles) == 2
    winding = cycles[0]
    assert winding.samples["A0"].sample_id == "session_1:10:A0"
    assert winding.samples["A4"].timestamp_unwrapped_us == 107
    assert winding.samples["A5"].timestamp_unwrapped_us == 119
    assert winding.a4_a5_pair_valid is True
    assert winding.a4_a5_skew_us == 12
    assert cycles[1].samples.keys() == {"A1"}
    assert cycles[1].a4_a5_pair_valid is False
    assert cycles[1].a4_a5_pair_reason == "missing A4 sample"


def test_unwraps_micros_uint32_rollover_without_changing_raw_timestamp():
    records = [
        parse(20, "A4", 0xFFFFFFFC),
        parse(20, "A5", 0xFFFFFFFE),
        parse(21, "A4", 3),
        parse(21, "A5", 8),
    ]

    cycles = align_aux_records(records)

    assert cycles[0].samples["A4"].timestamp_us == 0xFFFFFFFC
    assert cycles[1].samples["A4"].timestamp_us == 3
    assert cycles[1].samples["A4"].timestamp_unwrapped_us == (1 << 32) + 3
    assert cycles[1].a4_a5_skew_us == 5


def test_rejects_small_backwards_timestamp_instead_of_guessing_order():
    records = [
        parse(1, "A4", 1000),
        parse(2, "A4", 900),
    ]

    with pytest.raises(AuxAlignmentError, match="moved backwards"):
        align_aux_records(records)


def test_rejects_duplicate_channel_in_one_acquisition_cycle():
    records = [
        parse(3, "A0", 100),
        parse(3, "A0", 101),
    ]

    with pytest.raises(AuxAlignmentError, match="duplicate channel A0"):
        align_aux_records(records)


def test_marks_phase_or_direction_mismatch_invalid_without_pairing():
    records = [
        parse(4, "A4", 100, phase="WINDING", direction="FWD"),
        parse(4, "A5", 105, phase="WINDING", direction="REV"),
    ]

    cycle = align_aux_records(records)[0]

    assert cycle.metadata_consistent is False
    assert cycle.a4_a5_pair_valid is False
    assert cycle.a4_a5_skew_us is None
    assert cycle.a4_a5_pair_reason == "cycle metadata mismatch"


def test_timestamp_unwrap_state_is_independent_per_session():
    records = [
        parse(1, "A4", 0xFFFFFFFE, session="s1"),
        parse(1, "A4", 5, session="s2"),
        parse(2, "A4", 2, session="s1"),
    ]

    cycles = align_aux_records(records)

    assert cycles[2].samples["A4"].timestamp_unwrapped_us == (1 << 32) + 2
    assert cycles[1].samples["A4"].timestamp_unwrapped_us == 5
