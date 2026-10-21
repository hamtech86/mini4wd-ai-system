"""Main UI benchmark preset metadata with executable backend mode mapping."""

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
    """Return true when the label maps to a supported type and control mode."""
    preset = get_benchmark_preset(label)
    return preset is not None and preset[1] in ("TERMINAL", "INPUT")
