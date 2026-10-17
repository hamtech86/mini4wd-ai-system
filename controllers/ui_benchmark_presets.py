"""Main UI benchmark preset metadata.

This mapping describes the canonical UI labels only. It does not add support
for a voltage-control mode in the benchmark execution backend.
"""

BENCHMARK_PRESETS = {
    "STD-T": ("STANDARD_3V30S", "TERMINAL"),
    "Full-T": ("FULL_PACKAGE", "TERMINAL"),
    "STD-I": ("STANDARD_3V30S", "INPUT"),
    "Full-I": ("FULL_PACKAGE", "INPUT"),
}


def get_benchmark_preset(label):
    """Return the canonical (benchmark type, voltage mode) pair or None."""
    return BENCHMARK_PRESETS.get(label)


def is_benchmark_mode_supported(label):
    """Only TERMINAL mode is executable until backend INPUT control exists."""
    preset = get_benchmark_preset(label)
    return preset is not None and preset[1] == "TERMINAL"
