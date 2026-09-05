from dataclasses import dataclass
from types import SimpleNamespace

from controllers.local_raw_log_breakin_controller import LocalRawLogBreakinController
from raw_log_library import RawLogLibrary


class FakeSerial:
    def __init__(self):
        self.raw_log = "STALE\n"
        self.reset_count = 0

    @property
    def has_raw_log(self):
        return bool(self.raw_log)

    def reset_raw_log(self):
        self.reset_count += 1
        self.raw_log = "INFO,START\nDATA,1,2,3\n"


@dataclass
class FakeSession:
    session_id: str = "session-123"
    firmware_version: str = "MOTOR_BREAKIN_V3"


class FakeLibrary(RawLogLibrary):
    def __init__(self, root):
        super().__init__(root)
        self.registered = []

    def register(self, record, raw_body, extension=".log"):
        self.registered.append((record, raw_body))
        return super().register(record, raw_body, extension)


def test_adapter_resets_collector_and_registers_session_linked_raw_log(tmp_path, monkeypatch):
    serial = FakeSerial()
    library = FakeLibrary(tmp_path)
    controller = LocalRawLogBreakinController(
        serial_controller=serial,
        raw_log_library=library,
    )
    controller.session = FakeSession()
    controller.active_instance_id = "INSTANCE-001"
    controller.active_recipe_name = "RECIPE-A"

    monkeypatch.setattr(controller.__class__.__bases__[0], "start", lambda self, recipe, instance_id=None, resume=False: "result")

    result = controller.start(SimpleNamespace(name="RECIPE-A"), instance_id="INSTANCE-001")

    assert result == "result"
    assert serial.reset_count == 1
    assert len(library.registered) == 1
    record, raw_body = library.registered[0]
    assert record.log_id == "MOTOR-000001"
    assert record.device_type == "MOTOR"
    assert record.device_instance_id == "INSTANCE-001"
    assert record.motor_id == "INSTANCE-001"
    assert record.measurement_session_id == "session-123"
    assert raw_body == "INFO,START\nDATA,1,2,3\n"
    assert controller.last_raw_log_id == "MOTOR-000001"


def test_adapter_persists_raw_log_when_breakin_fails(tmp_path, monkeypatch):
    serial = FakeSerial()
    library = FakeLibrary(tmp_path)
    controller = LocalRawLogBreakinController(serial_controller=serial, raw_log_library=library)
    controller.session = FakeSession()
    controller.active_instance_id = "INSTANCE-002"
    controller.active_recipe_name = "RECIPE-B"

    def fail(self, recipe, instance_id=None, resume=False):
        raise RuntimeError("break-in failed")

    monkeypatch.setattr(controller.__class__.__bases__[0], "start", fail)

    try:
        controller.start(SimpleNamespace(name="RECIPE-B"), instance_id="INSTANCE-002")
    except RuntimeError as exc:
        assert str(exc) == "break-in failed"
    else:
        raise AssertionError("expected break-in failure")

    assert len(library.registered) == 1
    assert library.registered[0][0].measurement_session_id == "session-123"
