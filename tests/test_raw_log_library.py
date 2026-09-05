from raw_log_library import RawLog, RawLogLibrary


def test_motor_log_id_is_allocated_after_existing_ids(tmp_path):
    library = RawLogLibrary(tmp_path)
    library.root.joinpath("index.csv").write_text(
        "log_id,device_type,device_model,firmware_version,device_instance_id,channel,motor_id,battery_id,measurement_session_id,acquired_at,measurement_condition,source_reference,raw_path,metadata_path,notes\n"
        "MOTOR-000001,MOTOR,,,,,,,,,,,legacy.log,legacy.json,\n"
        "MOTOR-000004,MOTOR,,,,,,,,,,,legacy4.log,legacy4.json,\n",
        encoding="utf-8",
    )

    record = RawLog(device_type="MOTOR")
    library.register(record, "INFO,TEST\r\nDATA,raw\n")

    assert record.log_id == "MOTOR-000005"
    assert library.read_raw(record.log_id) == "INFO,TEST\r\nDATA,raw\n"


def test_battery_sequence_is_independent(tmp_path):
    library = RawLogLibrary(tmp_path)

    first = RawLog(device_type="MOTOR")
    battery = RawLog(device_type="BATTERY")
    second = RawLog(device_type="MOTOR")
    library.register(first, "motor-1\n")
    library.register(battery, "battery-1\n")
    library.register(second, "motor-2\n")

    assert first.log_id == "MOTOR-000001"
    assert second.log_id == "MOTOR-000002"
    assert battery.log_id == "BATTERY-000001"


def test_existing_storage_id_is_not_reissued(tmp_path):
    library = RawLogLibrary(tmp_path)
    motor_dir = tmp_path / "motor" / "UNASSIGNED"
    motor_dir.mkdir(parents=True)
    (motor_dir / "MOTOR-000003.log").write_text("legacy\n", encoding="utf-8")

    record = RawLog(device_type="MOTOR")
    library.register(record, "new\n")

    assert record.log_id == "MOTOR-000004"


def test_caller_cannot_supply_new_log_id_and_metadata_cannot_change_it(tmp_path):
    library = RawLogLibrary(tmp_path)

    try:
        library.register(RawLog(log_id="MOTOR-999999", device_type="MOTOR"), "x\n")
    except ValueError:
        pass
    else:
        raise AssertionError("caller-supplied new log_id must be rejected")

    record = RawLog(device_type="MOTOR")
    library.register(record, "original\n")
    original_id = record.log_id
    original_body = library.read_raw(original_id)

    library.update_metadata(original_id, notes="edited")

    assert library.get(original_id)[0].log_id == original_id
    assert library.read_raw(original_id) == original_body

    try:
        library.update_metadata(original_id, log_id="MOTOR-123456")
    except ValueError:
        pass
    else:
        raise AssertionError("log_id must be immutable")


def test_list_by_session(tmp_path):
    library = RawLogLibrary(tmp_path)
    record = RawLog(device_type="MOTOR", measurement_session_id="session-1")
    library.register(record, "raw\n")

    assert [item.log_id for item in library.list_by_session("session-1")] == [record.log_id]
    assert library.list_by_session("other") == []
