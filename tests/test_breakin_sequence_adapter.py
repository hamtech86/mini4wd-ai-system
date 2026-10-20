from controllers.breakin_sequence_adapter import BreakinSequenceAdapter
from controllers.sequence import SequenceDefinition


def test_sequence_is_translated_to_breakin_phase():
    sequence = SequenceDefinition(
        sequence_id="01_FWD",
        order=1,
        command="FWD",
        direction="FWD",
        pwm=64,
        duration_sec=60,
        parameters={
            "control": "VOLTAGE",
            "target_voltage": 4.0,
            "pwm_min": 35,
            "pwm_max": 120,
        },
    )
    phase = BreakinSequenceAdapter.to_phase(sequence)
    assert phase.name == "01_FWD"
    assert phase.direction == "FWD"
    assert phase.pwm == 64
    assert phase.duration_sec == 60
    assert phase.control == "VOLTAGE"
    assert phase.target_voltage == 4.0


def test_sequence_metadata_preserves_input_voltage_control_mode():
    sequence = SequenceDefinition(
        sequence_id="06_REV_3V_START", order=6, command="REV", direction="REV",
        parameters={"control": "VOLTAGE", "target_voltage": 3.0},
        metadata={"voltage_control_mode": "INPUT"},
    )
    phase = BreakinSequenceAdapter.to_phase(sequence)
    assert phase.metadata["voltage_control_mode"] == "INPUT"
