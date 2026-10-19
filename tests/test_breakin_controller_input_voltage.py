from controllers.breakin_controller import BreakinController
from controllers.recipe import BreakinPhase


class SerialStub:
    def __init__(self):
        self.pwm_values = []

    def set_pwm(self, pwm):
        self.pwm_values.append(pwm)


def controller():
    serial = SerialStub()
    instance = BreakinController(serial_controller=serial)
    instance.current_pwm = 60
    return instance, serial


def test_input_voltage_control_uses_v4_for_forward():
    instance, serial = controller()
    phase = BreakinPhase(
        name="FWD_INPUT", direction="FWD", control="VOLTAGE",
        target_voltage=3.0, pwm_min=35, pwm_max=120,
        metadata={"voltage_control_mode": "INPUT"},
    )
    instance._voltage_control(phase, {
        "voltage1": 2.0, "voltage2": 4.0, "motor_voltage": -2.0,
    })
    assert instance.current_pwm == 80
    assert serial.pwm_values == [80]


def test_input_voltage_control_uses_v5_for_reverse():
    instance, serial = controller()
    phase = BreakinPhase(
        name="REV_INPUT", direction="REV", control="VOLTAGE",
        target_voltage=3.0, pwm_min=35, pwm_max=120,
        metadata={"voltage_control_mode": "INPUT"},
    )
    instance._voltage_control(phase, {
        "voltage1": 4.0, "voltage2": 2.0, "motor_voltage": -2.0,
    })
    assert instance.current_pwm == 80
    assert serial.pwm_values == [80]


def test_voltage_ramp_preserves_input_control_mode():
    instance, serial = controller()
    phase = BreakinPhase(
        name="REV_RAMP", direction="REV", control="VOLTAGE_RAMP",
        start_voltage=3.0, end_voltage=9.0, duration_sec=60,
        pwm_min=35, pwm_max=120,
        metadata={"voltage_control_mode": "INPUT"},
    )
    instance.measurements.append({
        "voltage1": 4.0, "voltage2": 2.0, "motor_voltage": -2.0,
    })
    instance._voltage_ramp_control(phase)
    assert instance.current_pwm == 80
    assert serial.pwm_values == [80]


def test_terminal_voltage_control_uses_directional_drop_for_reverse():
    instance, serial = controller()
    phase = BreakinPhase(
        name="REV_TERMINAL", direction="REV", control="VOLTAGE",
        target_voltage=3.0, pwm_min=35, pwm_max=120,
    )
    instance._voltage_control(phase, {"motor_voltage": -2.0})
    assert instance.current_pwm == 80
    assert serial.pwm_values == [80]
