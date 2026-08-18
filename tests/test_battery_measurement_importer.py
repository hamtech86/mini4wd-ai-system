import sqlite3

from measurement.battery_measurement_importer import BatteryMeasurementImporter
from measurement.measurement import Measurement


def test_battery_import_persists_frame_without_changing_measurement_values():
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    columns = ", ".join(f.name + " REAL" for f in __import__('dataclasses').fields(Measurement) if f.name != 'record_type')
    db.execute("CREATE TABLE measurement (record_type TEXT, " + columns + ")")
    db.commit()

    importer = BatteryMeasurementImporter(db)
    measurement = importer.import_frame(
        "DATA,BATTERY_DISCHARGER_V1,CH1,12500,4.982,1.284,0,73,0,RUN",
        "SESSION-CH1",
    )

    row = db.execute("SELECT * FROM measurement").fetchone()
    assert row["session_id"] == "SESSION-CH1"
    assert row["instance_id"] == "CH1"
    assert row["current1"] == 4.982
    assert row["voltage1"] == 1.284
    assert row["power"] == 4.982 * 1.284
    assert row["pwm"] == 73
    assert measurement.session_id == "SESSION-CH1"
