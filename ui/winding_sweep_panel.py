"""Qt UI for the Python-coordinated 310-second winding PWM sweep."""
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtWidgets import (
    QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QVBoxLayout, QWidget,
)

from controllers.winding_pwm_sweep_controller import WindingPwmSweepController
from raw_log_library.manager import RawLog, RawLogLibrary
from raw_log_library.v2_store import RawLogV2Store


class WindingSweepPanel(QGroupBox):
    """Non-blocking UI adapter; all sweep progression is driven by QTimer."""

    def __init__(self, parent, root: Path, get_instance_id, get_breakin_controller):
        super().__init__("④ 巻線 PWM スイープ / RawLog v2")
        self.owner = parent
        self.root = Path(root)
        self.get_instance_id = get_instance_id
        self.get_breakin_controller = get_breakin_controller
        self.library = RawLogLibrary(self.root / "data" / "raw_logs")
        self.store = None
        self.controller = None
        self.log_id = None
        self.measurement_session_id = None
        self._record_registered = False

        layout = QVBoxLayout(self)
        status = QGridLayout()
        self.status = QLabel("READY")
        self.log_label = QLabel("LOG: --")
        self.instance_label = QLabel("INSTANCE: --")
        self.stage_label = QLabel("PWM: -- / 30")
        self.elapsed_label = QLabel("ELAPSED: --")
        self.package_label = QLabel("PACKAGE: NOT CREATED")
        for row, (name, widget) in enumerate((
            ("STATUS", self.status),
            ("LOG", self.log_label),
            ("MOTOR INSTANCE", self.instance_label),
            ("STAGE", self.stage_label),
            ("ELAPSED", self.elapsed_label),
            ("RAWLOG", self.package_label),
        )):
            status.addWidget(QLabel(name + ":"), row // 2, (row % 2) * 2)
            status.addWidget(widget, row // 2, (row % 2) * 2 + 1)
        layout.addLayout(status)

        controls = QHBoxLayout()
        self.start_button = QPushButton("START SWEEP 0–30")
        self.start_button.clicked.connect(self.start_sweep)
        self.stop_button = QPushButton("STOP SWEEP")
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_sweep)
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        self.library_button = QPushButton("RAWLOG LIBRARY / HISTORY")
        self.library_button.clicked.connect(self.open_library)
        controls.addWidget(self.library_button)
        layout.addLayout(controls)

        observation = QHBoxLayout()
        observation.addWidget(QLabel("回転目視ラベル（任意）"))
        self.rotation_label = QComboBox()
        self.rotation_label.addItem("記録しない", None)
        self.rotation_label.addItem("回転なし", "NO_ROTATION")
        self.rotation_label.addItem("回転あり", "ROTATION")
        self.rotation_label.addItem("不明", "UNKNOWN")
        observation.addWidget(self.rotation_label, 1)
        self.note = QLabel("目視ラベルは任意注釈。測定値・Derived値には混入しません。")
        self.note.setWordWrap(True)
        observation.addWidget(self.note, 2)
        self.observe_button = QPushButton("注釈を記録")
        self.observe_button.setEnabled(False)
        self.observe_button.clicked.connect(self.record_observation)
        observation.addWidget(self.observe_button)
        layout.addLayout(observation)

        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.tick)

    def _set_running_controls(self, running: bool):
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.observe_button.setEnabled(running)
        instance_widget = getattr(self.owner, "instance", None)
        if instance_widget is not None:
            instance_widget.setEnabled(not running)
        for name in ("start", "manager", "recipe"):
            widget = getattr(self.owner, name, None)
            if widget is not None:
                widget.setEnabled(not running)
        emergency_button = getattr(self.owner, "stop", None)
        if emergency_button is not None:
            emergency_button.setEnabled(running)

    def start_sweep(self):
        instance_id = self.get_instance_id()
        if instance_id is None:
            QMessageBox.warning(self, "Winding Sweep", "Motor Instanceを選択してください。")
            return

        breakin = self.get_breakin_controller()
        if breakin is None:
            QMessageBox.warning(self, "Winding Sweep", "BreakinControllerがありません。")
            return
        if getattr(breakin, "running", False):
            QMessageBox.warning(self, "Winding Sweep", "既存のBreak-in/Benchmark実行中は開始できません。")
            return
        serial_controller = getattr(breakin, "serial", None)
        if serial_controller is None or not getattr(serial_controller, "connected", False):
            QMessageBox.warning(self, "Winding Sweep", "既存のモーターUARTが接続されていません。")
            return
        if not getattr(serial_controller, "identity_verified", False):
            QMessageBox.warning(self, "Winding Sweep", "FW identity未確認のため開始できません。")
            return
        stop_check = getattr(serial_controller, "_stop_requested", None)
        if callable(stop_check) and stop_check():
            QMessageBox.warning(self, "Winding Sweep", "STOPラッチ中です。新しいアプリケーションセッションが必要です。")
            return

        info = getattr(serial_controller, "device_info", None) or {}
        required = ("TYPE", "MODEL", "FW", "BUILD", "ID")
        if any(not isinstance(info.get(key), str) or not info[key].strip() for key in required):
            QMessageBox.warning(self, "Winding Sweep", "FW identity情報が不完全です。")
            return
        if info.get("TYPE") != "MOTOR" or info.get("MODEL") != "MOTOR_BREAKIN_V3":
            QMessageBox.warning(self, "Winding Sweep", "対象外デバイスです。")
            return

        session_id = str(uuid.uuid4())
        acquired_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
        record = RawLog(
            device_type="MOTOR",
            device_model=info["MODEL"],
            firmware_version=info["FW"],
            device_instance_id=str(instance_id),
            motor_id=str(instance_id),
            measurement_session_id=session_id,
            acquired_at=acquired_at,
            measurement_condition="WINDING_PWM_SWEEP_0_30; 31 stages x 10 seconds; Python orchestrated",
            notes=f"RawLog v2 winding sweep; firmware_device_id={info['ID']}; DATA wire lines retained without DATA26 field promotion",
        )
        try:
            # The common RawLog Library allocates the canonical MOTOR-xxxxxx ID.
            self.library.register_v2_reference(record)
            self.log_id = record.log_id
            self._record_registered = True
            self.measurement_session_id = session_id
            self.store = RawLogV2Store(self.root / "data" / "raw_logs_v2")
            self.controller = WindingPwmSweepController(serial_controller, self.store)
            started = self.controller.start(
                log_id=self.log_id,
                measurement_session_id=session_id,
                measurement_plan_id="WINDING_PWM_SWEEP_0_30",
                motor_instance_id=str(instance_id),
            )
            self.log_label.setText("LOG: " + self.log_id)
            self.instance_label.setText("INSTANCE: " + str(instance_id))
            if not started:
                self._sync_library_metadata()
                self.status.setText("FAULTED / START REJECTED")
                self.package_label.setText("PACKAGE: FAULTED")
                return
        except Exception as exc:
            if self.controller is not None and self.controller.active:
                try:
                    self.controller.emergency_stop("START_EXCEPTION")
                except Exception:
                    pass
            if self.log_id:
                try:
                    self._sync_library_metadata(f"START_FAILED: {type(exc).__name__}: {exc}")
                except Exception:
                    pass
            QMessageBox.critical(self, "Winding Sweep", f"開始に失敗しました。\n{type(exc).__name__}: {exc}")
            self.status.setText("START FAILED")
            return

        self.rotation_label.setCurrentIndex(0)
        self.status.setText("RUNNING")
        self.package_label.setText("PACKAGE: STARTED")
        self._set_running_controls(True)
        self.timer.start()

    def open_library(self):
        try:
            from ui.raw_log_database_manager import RawLogDatabaseManager
            self.library_window = RawLogDatabaseManager(self.owner)
            self.library_window.setAttribute(Qt.WA_DeleteOnClose, True)
            self.library_window.show()
            self.library_window.raise_()
            self.library_window.activateWindow()
        except Exception as exc:
            QMessageBox.critical(self, "RawLog Library", f"Libraryを開けません。\\n{type(exc).__name__}: {exc}")

    def tick(self):
        if self.controller is None:
            self.timer.stop()
            return
        snapshot = self.controller.tick()
        self.status.setText(str(snapshot.get("status", "UNKNOWN")))
        self.stage_label.setText(
            f"PWM: {snapshot.get('pwm', '--')} / 30  ({int(snapshot.get('stage_index', -1)) + 1}/31)"
        )
        self.elapsed_label.setText(f"ELAPSED: {float(snapshot.get('elapsed_seconds', 0.0)):.1f} s")
        if not self.controller.active:
            self.timer.stop()
            self._sync_library_metadata()
            self._set_running_controls(False)
            final_status = self._manifest_status()
            self.package_label.setText("PACKAGE: " + final_status)
            self.status.setText(final_status + " / command-path result only")

    def stop_sweep(self):
        if self.controller is None or not self.controller.active:
            return
        self.status.setText("STOP REQUESTED")
        ok = self.controller.stop("USER_STOP")
        self.timer.stop()
        self._sync_library_metadata()
        self._set_running_controls(False)
        status = self._manifest_status()
        self.package_label.setText("PACKAGE: " + status)
        self.status.setText((status if ok else "STOP RESULT UNKNOWN") + " / physical stop not inferred")


    def emergency_stop(self):
        if self.controller is None or not self.controller.active:
            return
        self.status.setText("EMERGENCY STOP REQUESTED")
        ok = self.controller.emergency_stop("OPERATOR_EMERGENCY_STOP")
        self.timer.stop()
        self._sync_library_metadata()
        self._set_running_controls(False)
        status = self._manifest_status()
        self.package_label.setText("PACKAGE: " + status)
        self.status.setText((status if ok else "STOP RESULT UNKNOWN") + " / physical stop not confirmed")

    def record_observation(self):
        if self.controller is None or not self.controller.active:
            return
        label = self.rotation_label.currentData()
        if label is None:
            return
        try:
            self.controller.record_rotation_observation(label)
            self.note.setText("目視注釈をRawLog v2 EVENTとして保存しました。")
        except Exception as exc:
            QMessageBox.warning(self, "Winding Sweep", f"注釈を保存できません。\n{type(exc).__name__}: {exc}")

    def _manifest_status(self):
        if not self.log_id:
            return "NOT CREATED"
        path = self.root / "data" / "raw_logs_v2" / self.log_id / "manifest.json"
        try:
            status = str(json.loads(path.read_text(encoding="utf-8")).get("status", "UNKNOWN"))
            return "INCOMPLETE" if status == "STARTED" else status
        except Exception:
            return "INCOMPLETE"

    def _sync_library_metadata(self, extra_note=""):
        if not self.log_id or not self._record_registered:
            return
        status = self._manifest_status()
        note = f"RawLog v2 status={status}"
        if extra_note:
            note += "; " + extra_note
        self.library.update_metadata(self.log_id, notes=note)
