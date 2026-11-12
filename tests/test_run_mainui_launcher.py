from run_mainui import main


def test_mainui_launcher_uses_shared_context_with_battery_controller(monkeypatch):
    import run_mainui

    battery_controller = object()
    context = {
        "serial_controller": object(),
        "breakin_controller": object(),
        "battery_serial_controller": battery_controller,
    }
    created = {}

    class FakeApplication:
        def __init__(self, args):
            created["application_args"] = args

        def exec_(self):
            return 17

    class FakeMainWindow:
        def __init__(self, context=None):
            created["context"] = context

        def show(self):
            created["shown"] = True

    monkeypatch.setattr(run_mainui, "build_application_context", lambda: context)
    monkeypatch.setattr(run_mainui, "QApplication", FakeApplication)
    monkeypatch.setattr(run_mainui, "MainWindow", FakeMainWindow)

    assert main() == 17
    assert created["context"] is context
    assert created["context"]["battery_serial_controller"] is battery_controller
    assert created["shown"] is True
