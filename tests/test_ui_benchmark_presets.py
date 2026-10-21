from controllers.ui_benchmark_presets import (
    BENCHMARK_PRESETS,
    get_benchmark_preset,
    is_benchmark_mode_supported,
)


def test_four_ui_presets_map_to_canonical_benchmark_and_voltage_modes():
    assert BENCHMARK_PRESETS == {
        "STD-T": ("STANDARD_3V30S", "TERMINAL"),
        "Full-T": ("FULL_PACKAGE", "TERMINAL"),
        "STD-I": ("STANDARD_3V30S", "INPUT"),
        "Full-I": ("FULL_PACKAGE", "INPUT"),
    }


def test_all_four_presets_have_supported_control_modes():
    assert is_benchmark_mode_supported("STD-T")
    assert is_benchmark_mode_supported("Full-T")
    assert is_benchmark_mode_supported("STD-I")
    assert is_benchmark_mode_supported("Full-I")
    assert not is_benchmark_mode_supported("UNKNOWN")


def test_unknown_preset_does_not_fall_back_to_a_benchmark():
    assert get_benchmark_preset("UNKNOWN") is None
