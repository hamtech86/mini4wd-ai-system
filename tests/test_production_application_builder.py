from pathlib import Path

from app.production_application_builder import ProductionApplicationBuilder


class MockSerial:
    def forward(self):
        pass

    def reverse(self):
        pass

    def set_pwm(self, pwm):
        pass

    def stop_breakin(self):
        pass

    def emergency_stop(self):
        pass


def test_production_builder_initializes_real_database(tmp_path):
    db_path = tmp_path / "mini4wd.db"

    builder = ProductionApplicationBuilder(
        serial_controller=MockSerial(),
        database_path=str(db_path),
    )
    controller = builder.build_breakin_controller()

    assert db_path.exists()
    assert controller.database.is_connected
    assert controller.session_manager is not None
    assert controller.measurement_repository is not None
    assert controller.database.table_exists("measurement_session")
    assert controller.database.table_exists("measurement")
