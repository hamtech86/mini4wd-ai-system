from PyQt5.QtWidgets import QDialog, QVBoxLayout, QFormLayout, QLabel, QDialogButtonBox


class SavedResultDialog(QDialog):
    """Read-only view of a saved measurement session/result."""
    def __init__(self, parent, db, session_id):
        super().__init__(parent)
        self.setWindowTitle(f"Saved Result — Session {session_id}")
        self.resize(620, 520)
        layout = QVBoxLayout(self)
        title = QLabel(f"Saved Result / Session {session_id}")
        title.setStyleSheet("font-size:18px;font-weight:bold;")
        layout.addWidget(title)
        form = QFormLayout()
        layout.addLayout(form)

        session = db.execute(
            "SELECT * FROM measurement_session WHERE session_id=?", (session_id,)
        ).fetchone()
        measurement = db.execute(
            "SELECT * FROM measurement WHERE session_id=? ORDER BY id DESC LIMIT 1",
            (str(session_id),),
        ).fetchone()

        if session:
            names = [d[0] for d in db.execute("PRAGMA table_info(measurement_session)").fetchall()]
            session = dict(zip(names, session))
            for key in ("instance_id", "device_type", "device_model", "firmware_version",
                        "analysis_version", "start_datetime", "end_datetime", "result"):
                if key in session:
                    form.addRow(key, QLabel("" if session[key] is None else str(session[key])))

        if measurement:
            names = [d[1] for d in db.execute("PRAGMA table_info(measurement)").fetchall()]
            measurement = dict(zip(names, measurement))
            title2 = QLabel("Latest Measurement")
            title2.setStyleSheet("font-weight:bold;margin-top:8px;")
            layout.addWidget(title2)
            for key, label in (("elapsed_time", "Elapsed"), ("motor_voltage", "Motor Voltage"),
                               ("current_avg", "Current"), ("power", "Power"),
                               ("pwm", "PWM"), ("direction", "Direction"),
                               ("state", "State"), ("motor_temperature", "Temperature"),
                               ("peak_current", "Peak Current"), ("peak_voltage", "Peak Voltage"),
                               ("brush_peak_current", "Brush Peak Current")):
                if key in measurement:
                    form.addRow(label, QLabel("" if measurement[key] is None else str(measurement[key])))

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
