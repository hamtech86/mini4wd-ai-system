from types import SimpleNamespace

from app.main import MainWindow


class Label:
    def __init__(self):
        self.value = None

    def setText(self, value):
        self.value = value


def test_main_high_side_current_displays_current1_not_current_avg():
    labels = {key: Label() for key in (
        "STEP", "PHASE", "DIR", "PWM", "VOLT", "CURRENT", "ELAPSED", "REMAIN"
    )}
    live = {key: Label() for key in ("DIR", "PWM", "RPM", "V", "A", "STATE", "TEMP", "Arduino")}
    result = SimpleNamespace(status="RUNNING", elapsed_sec=1.2, sequence_id="step-1")
    fake = SimpleNamespace(
        sequence_executor=SimpleNamespace(
            progress=lambda: 0.5,
            state=SimpleNamespace(sequence_index=0),
            results=[result],
            remaining_sec=lambda: 2.3,
        ),
        sequence_selected_total=1,
        sequence_selected_ids={"step-1"},
        breakin_controller=SimpleNamespace(
            measurement_manager=SimpleNamespace(
                last_measurement=SimpleNamespace(
                    current1=0.123,
                    current_avg=0.456,
                    motor_voltage=2.34,
                    motor_temperature=25.0,
                )
            )
        ),
        run_state=Label(),
        progress=labels,
        live=live,
        sequence_status=Label(),
    )

    MainWindow._update_sequence_main_ui(fake, SimpleNamespace(
        sequence_id="step-1", direction="FWD", pwm=120
    ))

    assert labels["CURRENT"].value == "0.123 A"
    assert live["A"].value == "0.123 A"
