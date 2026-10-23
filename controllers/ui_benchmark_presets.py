"""Main UI benchmark preset metadata with executable backend mode mapping."""

# Project scope: INPUT control only. TERMINAL presets are intentionally excluded.
BENCHMARK_PRESETS = {
    "STD-I": ("STANDARD_3V30S", "INPUT"),
    "Full-I": ("FULL_PACKAGE", "INPUT"),
}


def get_benchmark_preset(label):
    """Return the canonical (benchmark type, voltage mode) pair or None."""
    return BENCHMARK_PRESETS.get(label)


def is_benchmark_mode_supported(label):
    """Return true only for the two supported INPUT-mode Benchmark presets."""
    preset = get_benchmark_preset(label)
    return preset is not None and preset[1] == "INPUT"
