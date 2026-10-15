from controllers.local_raw_log_breakin_controller import LocalRawLogBreakinController
from raw_log_library import RawLogLibrary


RECIPES = [
    ("STD-T", "STANDARD", "TERMINAL"),
    ("Full-T", "FULL_PACKAGE", "TERMINAL"),
    ("STD-I", "STANDARD", "INPUT"),
    ("Full-I", "FULL_PACKAGE", "INPUT"),
]


class FakeSerial:
    device_info = {
        "TYPE": "MOTOR",
        "MODEL": "MOTOR_BREAKIN_V3",
        "FW": "3.00",
        "BUILD": "TEST-BUILD",
        "ID": "TEST-DEVICE",
    }
    raw_log = ""

    def require_identified_device(self):
        return None


def test_all_recipes_persist_exact_raw_body_and_recipe_metadata(tmp_path):
    library = RawLogLibrary(tmp_path)
    serial = FakeSerial()
    raw_body = "DATA,raw-bytes,including,original,format\r\n"

    registered_ids = []
    for index, (recipe_name, benchmark_type, control_mode) in enumerate(RECIPES, start=1):
        controller = LocalRawLogBreakinController(
            serial_controller=serial,
            raw_log_library=library,
        )
        controller.active_instance_id = f"INSTANCE-{index:03d}"
        controller.active_recipe_name = recipe_name
        controller.benchmark_type = benchmark_type
        controller.voltage_control_mode = control_mode
        controller.benchmark_purpose = "MEASUREMENT"

        record = controller._register_raw_log(raw_body)

        registered_ids.append(record.log_id)
        assert record.log_id.startswith("MOTOR-")
        assert library.read_raw(record.log_id) == raw_body

        stored, raw_path, metadata_path = library.get(record.log_id)
        assert raw_path.is_file()
        assert metadata_path.is_file()
        assert stored.device_instance_id == f"INSTANCE-{index:03d}"
        assert stored.measurement_condition == benchmark_type
        assert f"recipe={recipe_name}" in stored.notes
        assert f"voltage_control_mode={control_mode}" in stored.notes

        # Read the metadata file independently of the in-memory RawLog object.
        import json
        persisted = json.loads(metadata_path.read_text(encoding="utf-8"))[record.log_id]
        assert persisted["measurement_condition"] == benchmark_type
        assert f"recipe={recipe_name}" in persisted["notes"]
        assert f"voltage_control_mode={control_mode}" in persisted["notes"]

        import csv
        with library.index_path.open("r", encoding="utf-8", newline="") as index_file:
            indexed = {row["log_id"]: row for row in csv.DictReader(index_file)}[record.log_id]
        assert indexed["measurement_condition"] == benchmark_type
        assert f"recipe={recipe_name}" in indexed["notes"]
        assert f"voltage_control_mode={control_mode}" in indexed["notes"]

    assert len(set(registered_ids)) == 4
    assert len(library.list_logs(device_type="MOTOR")) == 4
