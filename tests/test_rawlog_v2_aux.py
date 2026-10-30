import pytest

from communication.rawlog_v2_aux import AuxParseError, parse_aux_line


VALID = "AUX,2,sess_20261031_0001,42,WINDING,FWD,0,MEASURE,A0,514,123456"


def test_parse_preserves_raw_adc_and_individual_timestamp():
    record = parse_aux_line(VALID + "\r\n")
    assert record.channel == "A0"
    assert record.adc_raw == 514
    assert record.timestamp_us == 123456
    assert record.sequence == 42
    assert record.raw_line == VALID


def test_all_confirmed_channels_are_accepted_independently():
    for channel in ("A0", "A1", "A4", "A5"):
        fields = VALID.split(",")
        fields[8] = channel
        assert parse_aux_line(",".join(fields)).channel == channel


@pytest.mark.parametrize("line", [
    "",
    "DATA," + ",".join(["0"] * 25),
    VALID + ",extra",
    "AUX,1,sess,1,WINDING,FWD,0,MEASURE,A0,500,100",
    "AUX,2,,1,WINDING,FWD,0,MEASURE,A0,500,100",
    "AUX,2,sess,1,WINDING,FWD,256,MEASURE,A0,500,100",
    "AUX,2,sess,1,WINDING,FWD,0,MEASURE,A2,500,100",
    "AUX,2,sess,1,WINDING,FWD,0,MEASURE,A0,1024,100",
    "AUX,2,sess,1,WINDING,FWD,0,MEASURE,A0,500,4294967296",
    "AUX,2,sess,-1,WINDING,FWD,0,MEASURE,A0,500,100",
    "AUX,2,sess,1,WINDING,SIDEWAYS,0,MEASURE,A0,500,100",
])
def test_invalid_records_are_rejected(line):
    with pytest.raises(AuxParseError):
        parse_aux_line(line)


def test_non_string_input_is_rejected():
    with pytest.raises(AuxParseError):
        parse_aux_line(None)
