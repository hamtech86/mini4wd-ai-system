from controllers.ui_benchmark_presets import (
    BENCHMARK_PRESETS,
    get_benchmark_preset,
    is_benchmark_mode_supported,
)


def test_only_std_i_and_full_i_are_supported_benchmark_presets():
    assert BENCHMARK_PRESETS == {
        "STD-I": ("STANDARD_3V30S", "INPUT"),
        "Full-I": ("FULL_PACKAGE", "INPUT"),
    }


def test_only_input_mode_presets_are_supported():
    assert is_benchmark_mode_supported("STD-I")
    assert is_benchmark_mode_supported("Full-I")
    assert not is_benchmark_mode_supported("STD-T")
    assert not is_benchmark_mode_supported("Full-T")
    assert not is_benchmark_mode_supported("UNKNOWN")


def test_unknown_or_excluded_preset_does_not_fall_back_to_a_benchmark():
    assert get_benchmark_preset("STD-T") is None
    assert get_benchmark_preset("Full-T") is None
    assert get_benchmark_preset("UNKNOWN") is None
