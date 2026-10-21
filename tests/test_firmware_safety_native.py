from pathlib import Path
import subprocess
import tempfile


def test_motor_firmware_stop_and_pause_safety_native_harness():
    repo_root = Path(__file__).resolve().parents[1]
    harness = repo_root / "tests" / "firmware_safety" / "test_motor_firmware_safety.cpp"
    include_dir = harness.parent

    with tempfile.TemporaryDirectory(prefix="motor-fw-safety-") as temp_dir:
        executable = Path(temp_dir) / "motor_firmware_safety_test"
        subprocess.run(
            [
                "g++",
                "-std=c++11",
                "-Wall",
                "-Wextra",
                "-I",
                str(include_dir),
                str(harness),
                "-o",
                str(executable),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            [str(executable)],
            check=True,
            capture_output=True,
            text=True,
        )
