"""Regression tests for strict motor INFO identity and RawLog exclusion."""
from communication.serial_controller import SerialController


class FakeSerial:
    def __init__(self, lines=()):
        self.lines = list(lines)
        self.writes = []
        self.timeout = 1
        self.closed = False

    @property
    def in_waiting(self):
        return bool(self.lines)

    def readline(self):
        return self.lines.pop(0) if self.lines else b""

    def write(self, payload):
        self.writes.append(payload.decode("utf-8").strip())

    def close(self):
        self.closed = True


VALID_INFO = "INFO,TYPE=MOTOR,MODEL=MOTOR_BREAKIN_V3,FW=3.00,BUILD=ACS-CAL-LOG-20261013-01,ID=MOTOR01"


def test_drive_commands_are_blocked_until_info_identity_is_verified():
    controller = SerialController()
    handle = FakeSerial()
    controller.serial = handle
    controller.connected = True

    assert controller.forward() is False
    assert controller.reverse() is False
    assert controller.set_pwm(60) is False
    assert handle.writes == []
    assert controller.set_pwm(0) == "PWM=0"
    assert controller.send_command("STOP") == "STOP"
    assert handle.writes == ["PWM=0", "STOP"]


def test_valid_info_verifies_expected_model_and_allows_extension_keys():
    controller = SerialController()
    line = VALID_INFO + ",EXTRA=reserved-for-future"
    controller.serial = FakeSerial([(line + "\n").encode("utf-8")])
    controller.connected = True

    assert controller._verify_info_response(timeout=0.1) is True
    assert controller.identity_verified is True
    assert controller.device_info["MODEL"] == "MOTOR_BREAKIN_V3"
    assert "EXTRA" not in controller.device_info


def test_wrong_info_model_does_not_verify_identity():
    controller = SerialController()
    line = VALID_INFO.replace("MODEL=MOTOR_BREAKIN_V3", "MODEL=BATTERY_DISCHARGE")
    controller.serial = FakeSerial([(line + "\n").encode("utf-8")])
    controller.connected = True

    assert controller._verify_info_response(timeout=0.1) is False
    assert controller.identity_verified is False


def test_info_rows_are_excluded_from_raw_log():
    controller = SerialController()
    data_line = "DATA," + ",".join(["0"] * 25)
    handle = FakeSerial([
        (VALID_INFO + "\n").encode("utf-8"),
        b"CAL,ACS1=2.50,ACS2=2.51\n",
        (data_line + "\n").encode("utf-8"),
    ])
    controller.serial = handle
    controller.connected = True

    assert controller.read_measurement() == data_line
    assert "INFO," not in controller.raw_log
    assert "CAL,ACS1=2.50,ACS2=2.51" in controller.raw_log
    assert data_line in controller.raw_log



def test_unexpected_info_during_armed_run_marks_reboot_and_revokes_token():
    controller = SerialController()
    controller.serial = FakeSerial([(VALID_INFO + "\n").encode("utf-8")])
    controller.connected = True
    controller.identity_verified = True
    controller.device_info = {"TYPE": "MOTOR", "MODEL": "MOTOR_BREAKIN_V3",
                              "FW": "3.03", "BUILD": "EXPLICIT-ARM-STOP-ACK-20261023-01",
                              "ID": "000001"}
    controller._active_arm_token = "DEADBEEF"

    assert controller.read_measurement() is None
    assert controller.device_reboot_detected is True
    assert "reboot suspected" in controller.device_reboot_reason.lower()
    assert controller.device_reboot_raw_line == VALID_INFO
    assert controller._active_arm_token is None
    assert controller.identity_verified is False
    assert controller.device_info is None
    assert "INFO," not in controller.raw_log


def test_info_during_idle_read_is_not_misclassified_as_reboot():
    controller = SerialController()
    controller.serial = FakeSerial([(VALID_INFO + "\n").encode("utf-8")])
    controller.connected = True

    assert controller.read_measurement() is None
    assert controller.device_reboot_detected is False
    assert controller.identity_verified is True



def test_missing_control_data_triggers_existing_three_sample_fail_safe():
    from types import SimpleNamespace
    from controllers.breakin_controller import BreakinController

    class MissingMeasurementManager:
        last_measurement = None

        def collect(self):
            return None

    class StopRecorder:
        device_reboot_detected = False

        def __init__(self):
            self.stop_calls = 0

        def emergency_stop(self):
            self.stop_calls += 1
            return {"pwm_zero": False, "stop_command": False, "disconnect": True, "errors": []}

    serial = StopRecorder()
    controller = BreakinController(serial, measurement_manager=MissingMeasurementManager())
    phase = SimpleNamespace(control="VOLTAGE", target_voltage=3.0,
                             start_voltage=None, end_voltage=None, direction="FWD")

    assert controller._collect_measurement(phase) is None
    assert controller._collect_measurement(phase) is None
    try:
        controller._collect_measurement(phase)
        assert False, "third consecutive missing control sample must abort"
    except RuntimeError as exc:
        assert "3 consecutive invalid control samples" in str(exc)
    assert serial.stop_calls == 1
    assert controller.emergency_stop_latched is True


def test_detected_reboot_aborts_even_when_measurement_is_missing():
    from types import SimpleNamespace
    from controllers.breakin_controller import BreakinController

    class MissingMeasurementManager:
        last_measurement = None

        def collect(self):
            return None

    class RebootedSerial:
        device_reboot_detected = True
        device_reboot_reason = "Unexpected INFO received during an armed run; firmware reboot suspected."

        def __init__(self):
            self.stop_calls = 0

        def emergency_stop(self):
            self.stop_calls += 1
            return {"pwm_zero": False, "stop_command": False, "disconnect": True, "errors": []}

    serial = RebootedSerial()
    controller = BreakinController(serial, measurement_manager=MissingMeasurementManager())
    phase = SimpleNamespace(control="VOLTAGE", target_voltage=3.0,
                             start_voltage=None, end_voltage=None, direction="FWD")

    try:
        controller._collect_measurement(phase)
        assert False, "detected reboot must abort immediately"
    except RuntimeError as exc:
        assert "firmware reboot detected" in str(exc).lower()
    assert serial.stop_calls == 1
    assert controller.emergency_stop_latched is True

def test_direct_controller_start_blocks_full_tunebasic_until_issue98_clearance():
    from types import SimpleNamespace
    from controllers.breakin_controller import BreakinController

    # The guard must run before controller state, serial, ARM, or PWM access.
    controller = BreakinController.__new__(BreakinController)
    recipe = SimpleNamespace(name="TUNE_BASIC", phases=[])

    try:
        controller.start(recipe)
        assert False, "direct full TuneBasic start must remain blocked by Issue #98"
    except RuntimeError as exc:
        assert "Issue #98" in str(exc)
    assert controller.FULL_TUNEBASIC_ENABLED is False


def test_initial_empty_serial_poll_waits_for_startup_run_data():
    """An initially empty serial poll is followed by a valid 26-field RUN DATA frame."""
    from measurement.measurement_manager import MeasurementManager

    # Exact protocol order: DATA plus the 25 fields in CSV_FIELDS.
    run_data = "DATA,MOTOR_BREAKIN_V3,000001,100,512,512,0.10,0.11,3.00,0.00,3.00,80,FWD,RUN,0.105,0.315,0.01,0.01,0.32,0.11,3.00,80,0.12,0,0,25.0"

    class StartupSerial:
        from communication.csv_parser import CSVParser
        parser = CSVParser()

        def __init__(self):
            # Represents the first poll occurring just before the next periodic
            # DATA frame, then the first actual RUN frame.
            self.frames = [None, run_data]
            self.calls = 0

        def read_measurement(self):
            self.calls += 1
            return self.frames.pop(0) if self.frames else None

    serial = StartupSerial()
    manager = MeasurementManager(serial)

    result = manager.collect()

    assert result is not None
    assert serial.calls == 2
    assert manager.last_rejection_reason is None
    assert getattr(result, "state", None) == "RUN" or (
        isinstance(result, dict) and result.get("state") == "RUN"
    )
