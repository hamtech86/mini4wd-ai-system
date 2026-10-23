"""Shared timed INPUT-voltage execution loop for benchmark and TuneBasic phases.

Keep the feedback/control iteration identical between the proven STD-I benchmark
and TuneBasic voltage phases. Recipe orchestration remains in each caller.
"""
import time


def run_timed_voltage_phase(controller, phase, duration_sec, *, save_checkpoint=False):
    """Run one voltage-controlled phase using the controller's common safety path."""
    controller.phase_started_at = time.time()
    controller.phase_elapsed_before_pause = 0.0
    while controller.running and controller._effective_elapsed() < float(duration_sec):
        if controller.paused:
            time.sleep(controller.CONTROL_INTERVAL_SEC)
            continue

        measurement = controller._collect_measurement(phase)
        if measurement is None:
            # Do not reuse stale feedback or treat a missing frame as a voltage.
            time.sleep(controller.CONTROL_INTERVAL_SEC)
            continue

        safety = controller._safety_violation(measurement)
        if safety:
            controller.abort_reason = safety
            controller.emergency_stop()
            return False

        controller._voltage_control(phase, measurement)
        if save_checkpoint:
            controller._save_checkpoint()
        time.sleep(controller.CONTROL_INTERVAL_SEC)

    return controller.running and not getattr(controller, "abort_reason", None)
