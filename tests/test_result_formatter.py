from analysis.models import AnalysisResult
from ui.result_formatter import format_analysis_result


def test_format_analysis_result_list_shows_score_and_rank():
    result = AnalysisResult()
    result.score.total_score = 82.35
    result.score.rank = "A"

    text = format_analysis_result([result, result])

    assert text == "RESULT: SCORE 82.4 / RANK A (2 samples)"


def test_format_analysis_result_handles_empty_list():
    assert format_analysis_result([]) == "RESULT: NO ANALYSIS"


def test_format_analysis_result_handles_none():
    assert format_analysis_result(None) == "RESULT: --"


def test_format_analysis_result_supports_legacy_dict():
    text = format_analysis_result(
        [{"score": {"total_score": 75, "rank": "B"}}]
    )

    assert text == "RESULT: SCORE 75.0 / RANK B (1 samples)"
