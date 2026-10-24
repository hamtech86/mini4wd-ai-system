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


def test_input_voltage_control_mode_survives_sequence_adapter():
    sequence = SequenceDefinition(
        sequence_id="06_REV_3V",
        order=6,
        command="FWD",
        direction="REV",
        pwm=64,
        duration_sec=30,
        parameters={"control": "VOLTAGE", "target_voltage": 3.0},
        metadata={"voltage_control_mode": "INPUT"},
    )
    phase = BreakinSequenceAdapter.to_phase(sequence)
    assert phase.metadata["voltage_control_mode"] == "INPUT"


class FakeSerial:
    def __init__(self, info, verified=True, arm_result=True):
        self.device_info = info
        self.identity_verified = verified
        self.arm_result = arm_result
        self.commands = []

    def arm(self):
        self.commands.append("ARM")
        return self.arm_result

    def forward(self):
        self.commands.append("FWD")

    def reverse(self):
        self.commands.append("REV")

    def set_pwm(self, pwm):
        self.commands.append(f"PWM={pwm}")


class FakeController:
    def __init__(self, serial):
        self.serial = serial


def _sequence():
    return SequenceDefinition(
        sequence_id="01_FWD",
        order=1,
        command="FWD",
        direction="FWD",
        pwm=64,
        duration_sec=10,
        parameters={"control": "PWM", "pwm_min": 35, "pwm_max": 120},
    )


def test_sequence_adapter_blocks_mismatched_firmware_before_arm_or_drive():
    serial = FakeSerial({
        "TYPE": "MOTOR",
        "MODEL": "MOTOR_BREAKIN_V3",
        "FW": "3.03",
        "BUILD": "OTHER-20261024-01",
    })
    adapter = BreakinSequenceAdapter(FakeController(serial))
    import pytest
    with pytest.raises(RuntimeError, match="exact authorized"):
        adapter.start_sequence(_sequence())
    assert serial.commands == []


def test_sequence_adapter_requires_exact_identity_and_explicit_arm():
    serial = FakeSerial({
        "TYPE": "MOTOR",
        "MODEL": "MOTOR_BREAKIN_V3",
        "FW": "3.03",
        "BUILD": "EXPLICIT-ARM-STOP-ACK-20261023-01",
    })
    adapter = BreakinSequenceAdapter(FakeController(serial))
    # Minimal controller helpers used to calculate initial PWM.
    adapter.controller._initial_pwm_for_voltage = lambda target, phase: 64
    adapter.start_sequence(_sequence())
    assert serial.commands[0] == "ARM"
    assert "FWD" in serial.commands
    assert "PWM=64" in serial.commands


def test_sequence_adapter_blocks_when_arm_is_not_acknowledged():
    serial = FakeSerial({
        "TYPE": "MOTOR",
        "MODEL": "MOTOR_BREAKIN_V3",
        "FW": "3.03",
        "BUILD": "EXPLICIT-ARM-STOP-ACK-20261023-01",
    }, arm_result=False)
    adapter = BreakinSequenceAdapter(FakeController(serial))
    import pytest
    with pytest.raises(RuntimeError, match="explicit ARM"):
        adapter.start_sequence(_sequence())
    assert serial.commands == ["ARM"]
