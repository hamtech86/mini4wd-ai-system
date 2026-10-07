from types import SimpleNamespace

from controllers.breakin_controller import BreakinController
from controllers.breakin_sequence_adapter import BreakinSequenceAdapter
from controllers.motor_benchmark import (
    FULL_I,
    FULL_T,
    INPUT,
    STD_I,
    STD_T,
    STANDARD,
    TERMINAL,
    build_benchmark_recipe,
    benchmark_recipe_spec,
    benchmark_phase_count,
    run_benchmark,
)
from controllers.recipe_engine import RecipeEngine
from measurement.measurement import Measurement


def make_measurement(direction="FWD", voltage1=3.0, voltage2=0.8, motor_voltage=2.2):
    return Measurement(
        record_type="DATA",
        device_model="MOTOR_BREAKIN_V3",
        instance_id="1",
        elapsed_time=1000,
        raw_acs1=0,
        raw_acs2=0,
        current1=0.1,
        current2=0.1,
        voltage1=voltage1,
        voltage2=voltage2,
        motor_voltage=motor_voltage,
        pwm=80,
        direction=direction,
        state="RUNNING",
        current_avg=0.1,
        power=0.22,
        current_ripple=0.01,
        voltage_ripple=0.01,
        peak_power=0.3,
        peak_current=0.2,
        peak_voltage=2.3,
        peak_pwm=80,
        brush_peak_current=0.2,
        raw_magnetic=0,
        magnetic_level=0.0,
        motor_temperature=25.0,
    )


def test_benchmark_phase_counts_cover_all_modes_and_legacy_aliases():
    assert benchmark_phase_count(STANDARD) == 2
    assert benchmark_phase_count("FULL_PACKAGE") == 6
    assert benchmark_phase_count(STD_T) == 2
    assert benchmark_phase_count(FULL_T) == 6
    assert benchmark_phase_count(STD_I) == 2
    assert benchmark_phase_count(FULL_I) == 6
    assert benchmark_phase_count("STANDARD_3V30S") == 2
    assert benchmark_phase_count("FULL_PACKAGE") == 6


def test_four_benchmark_recipe_axes_are_explicit():
    assert benchmark_recipe_spec(STD_T) == (STD_T, STANDARD, TERMINAL)
    assert benchmark_recipe_spec(FULL_T) == (FULL_T, "FULL_PACKAGE", TERMINAL)
    assert benchmark_recipe_spec(STD_I) == (STD_I, STANDARD, INPUT)
    assert benchmark_recipe_spec(FULL_I) == (FULL_I, "FULL_PACKAGE", INPUT)


def test_benchmark_recipe_objects_keep_both_axes():
    for name in (STD_T, FULL_T, STD_I, FULL_I):
        recipe = build_benchmark_recipe(name)
        assert recipe.benchmark_type in {STANDARD, "FULL_PACKAGE"}
        assert recipe.voltage_control_mode in {TERMINAL, INPUT}
        assert all(
            phase.metadata["voltage_control_mode"] == recipe.voltage_control_mode
            for phase in recipe.phases
        )


def test_input_voltage_is_direction_aware_without_changing_raw_fields():
    fwd = make_measurement("FWD", voltage1=3.1, voltage2=0.9, motor_voltage=2.2)
    rev = make_measurement("REV", voltage1=0.9, voltage2=3.1, motor_voltage=2.2)
    assert fwd.input_voltage == 3.1
    assert rev.input_voltage == 3.1
    assert fwd.motor_voltage == 2.2
    assert rev.motor_voltage == 2.2


def test_input_control_uses_v4_fwd_and_v5_rev():
    serial = SimpleNamespace(set_pwm=lambda pwm: None)
    controller = BreakinController(serial)
    controller.voltage_control_mode = INPUT
    controller.current_pwm = 90
    phase_fwd = SimpleNamespace(direction="FWD", target_voltage=3.0, pwm_min=35, pwm_max=120)
    phase_rev = SimpleNamespace(direction="REV", target_voltage=3.0, pwm_min=35, pwm_max=120)

    fwd = make_measurement("FWD", voltage1=2.0, voltage2=0.4, motor_voltage=1.6)
    rev = make_measurement("REV", voltage1=0.4, voltage2=2.0, motor_voltage=1.6)

    assert controller._controlled_voltage(phase_fwd, fwd) == 2.0
    assert controller._controlled_voltage(phase_rev, rev) == 2.0


def test_terminal_control_still_uses_motor_voltage():
    serial = SimpleNamespace(set_pwm=lambda pwm: None)
    controller = BreakinController(serial)
    controller.voltage_control_mode = TERMINAL
    phase = SimpleNamespace(direction="FWD", target_voltage=3.0, pwm_min=35, pwm_max=120)
    measurement = make_measurement("FWD", voltage1=3.0, voltage2=0.4, motor_voltage=2.6)
    assert controller._controlled_voltage(phase, measurement) == 2.6


def test_sequence_adapter_preserves_input_mode():
    serial = SimpleNamespace(
        forward=lambda: None,
        reverse=lambda: None,
        set_pwm=lambda pwm: None,
    )
    controller = BreakinController(serial)
    adapter = BreakinSequenceAdapter(controller)
    sequence = SimpleNamespace(
        direction="REV",
        pwm=80,
        duration_sec=1,
        sequence_id="01_TEST",
        parameters={
            "control": "VOLTAGE",
            "target_voltage": 3.0,
            "pwm_min": 35,
            "pwm_max": 120,
            "voltage_control_mode": INPUT,
            "benchmark_type": "STANDARD",
        },
        metadata={},
    )
    adapter.start_sequence(sequence)
    assert controller.voltage_control_mode == INPUT
    assert controller.benchmark_type == STANDARD


def test_remaining_time_uses_sequence_executor_authoritative_value():
    serial = SimpleNamespace(set_pwm=lambda pwm: None)
    controller = BreakinController(serial)
    adapter = BreakinSequenceAdapter(controller)
    from controllers.sequence_executor import SequenceExecutor
    executor = SequenceExecutor(adapter=adapter)
    executor.sequences = [SimpleNamespace(sequence_id="01", enabled=True, duration_sec=30)]
    executor.results = [SimpleNamespace(status="RUNNING", remaining_sec=17.5, sequence_id="01")]
    executor.state = SimpleNamespace(sequence_index=0)
    controller.current_phase = SimpleNamespace(direction="FWD", duration_sec=30)
    snapshot = controller.execution_snapshot()
    assert snapshot["remaining_time"] == 17.5


def test_recipe_engine_resolves_four_benchmark_recipes():
    engine = RecipeEngine()
    for name in (STD_T, FULL_T, STD_I, FULL_I):
        recipe = engine.get(name)
        assert recipe is not None
        assert recipe.name == name
