"""Qt UI adapter for the Python-coordinated 310-second winding PWM sweep."""
from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

from PyQt5.QtCore import QObject, QThread, QTimer, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QVBoxLayout,
)

from controllers.winding_pwm_sweep_controller import WindingPwmSweepController
from raw_log_library.manager import RawLog, RawLogLibrary
from raw_log_library.v2_store import RawLogV2Store


class WindingSweepWorker(QObject):
    """Owns all serial/controller work on a dedicated Qt worker thread."""

    started = pyqtSignal(bool, str)
    progress = pyqtSignal(dict)
    completed = pyqtSignal(str, str)
    observation_result = pyqtSignal(bool, str)

    def __init__(self, controller, log_id, package_root, start_args):
        super().__init__()
        self.controller = controller
        self.log_id = log_id
        self.package_root = Path(package_root)
        self.start_args = dict(start_args)
        self._completed = False

    @pyqtSlot()
    def start(self):
        try:
            ok = self.controller.start(**self.start_args)
            self.started.emit(bool(ok), "" if ok else "START_REJECTED")
            if not ok:
                self._complete("START_REJECTED")
        except Exception as exc:
            if self.controller.active:
                try:
                    self.controller.emergency_stop("START_EXCEPTION")
                except Exception:
                    pass
            self.started.emit(False, f"{type(exc).__name__}: {exc}")
            self._complete(f"START_EXCEPTION: {type(exc).__name__}: {exc}")

    @pyqtSlot()
    def tick(self):
        if self._completed or not self.controller.active:
            self._complete("")
            return
        snapshot = self.controller.tick()
        self.progress.emit(snapshot)
        if not self.controller.active:
            self._complete("")

    @pyqtSlot(str)
    def observe(self, label):
        if self._completed or not self.controller.active:
            self.observation_result.emit(False, "Sweep is not active.")
            return
        try:
            self.controller.record_rotation_observation(label)
            self.observation_result.emit(True, "目視注釈をRawLog v2 EVENTとして保存しました。")
        except Exception as exc:
            self.observation_result.emit(False, f"{type(exc).__name__}: {exc}")

    @pyqtSlot()
    def stop(self):
        if self._completed:
            return
        if self.controller.active:
            ok = self.controller.stop("USER_STOP")
            self._complete("" if ok else "STOP_RESULT_UNKNOWN")
        else:
            self._complete("STOP_REQUESTED_BEFORE_ACTIVE")

    @pyqtSlot()
    def emergency_stop(self):
        if self._completed:
            return
        if self.controller.active:
            ok = self.controller.emergency_stop("OPERATOR_EMERGENCY_STOP")
            self._complete("" if ok else "STOP_RESULT_UNKNOWN")
        else:
            # The start slot is serialized ahead of this queued request. If it
            # never made the package active, preserve the visible incomplete state.
            self._complete("EMERGENCY_STOP_REQUESTED")

    def _complete(self, detail):
        if self._completed:
            return
        self._completed = True
        path = self.package_root / self.log_id / "manifest.json"
        try:
            status = str(json.loads(path.read_text(encoding="utf-8")).get("status", "UNKNOWN"))
            if status == "STARTED":
                status = "INCOMPLETE"
        except Exception:
            status = "INCOMPLETE"
        self.completed.emit(status, detail)


class WindingSweepPanel(QGroupBox):
    """Non-blocking UI adapter; timer only queues work to the serial worker."""

    start_requested = pyqtSignal()
    tick_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    emergency_requested = pyqtSignal()
    observe_requested = pyqtSignal(str)

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
        self._tick_pending = False
        self._thread = None
        self._worker = None

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
        self.timer.timeout.connect(self._queue_tick)

    def _set_running_controls(self, running: bool):
        self.start_button.setEnabled(not running)
        self.stop_button.setEnabled(running)
        self.observe_button.setEnabled(False)
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

    def _start_worker(self, serial_controller, start_args):
        self._thread = QThread(self)
        self._worker = WindingSweepWorker(
            self.controller,
            self.log_id,
            self.root / "data" / "raw_logs_v2",
            start_args,
        )
        self._worker.moveToThread(self._thread)
        self.start_requested.connect(self._worker.start, Qt.QueuedConnection)
        self.tick_requested.connect(self._worker.tick, Qt.QueuedConnection)
        self.stop_requested.connect(self._worker.stop, Qt.QueuedConnection)
        self.emergency_requested.connect(self._worker.emergency_stop, Qt.QueuedConnection)
        self.observe_requested.connect(self._worker.observe, Qt.QueuedConnection)
        self._worker.started.connect(self._on_worker_started)
        self._worker.progress.connect(self._on_progress)
        self._worker.completed.connect(self._on_worker_completed)
        self._worker.observation_result.connect(self._on_observation_result)
        self._worker.completed.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._on_worker_thread_finished)
        self._thread.start()
        self.start_requested.emit()

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
            self.library.register_v2_reference(record)
            self.log_id = record.log_id
            self._record_registered = True
            self.measurement_session_id = session_id
            self.store = RawLogV2Store(self.root / "data" / "raw_logs_v2")
            self.controller = WindingPwmSweepController(serial_controller, self.store)
            start_args = {
                "log_id": self.log_id,
                "measurement_session_id": session_id,
                "measurement_plan_id": "WINDING_PWM_SWEEP_0_30",
                "motor_instance_id": str(instance_id),
            }
            self.log_label.setText("LOG: " + self.log_id)
            self.instance_label.setText("INSTANCE: " + str(instance_id))
            self.rotation_label.setCurrentIndex(0)
            self.status.setText("STARTING")
            self.package_label.setText("PACKAGE: STARTING")
            self._set_running_controls(True)
            self._start_worker(serial_controller, start_args)
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
            self._set_running_controls(False)
            QMessageBox.critical(self, "Winding Sweep", f"開始に失敗しました。\n{type(exc).__name__}: {exc}")
            self.status.setText("START FAILED")

    def _on_worker_started(self, ok, detail):
        if ok:
            self.observe_button.setEnabled(True)
            self.status.setText("RUNNING")
            self.package_label.setText("PACKAGE: STARTED")
            self.timer.start()
            return
        self.status.setText("START FAILED / " + (detail or "UNKNOWN"))
        self.timer.stop()

    def _queue_tick(self):
        if self._tick_pending or self._worker is None:
            return
        self._tick_pending = True
        self.tick_requested.emit()

    def _on_progress(self, snapshot):
        self._tick_pending = False
        self.status.setText(str(snapshot.get("status", "UNKNOWN")))
        self.stage_label.setText(
            f"PWM: {snapshot.get('pwm', '--')} / 30  ({int(snapshot.get('stage_index', -1)) + 1}/31)"
        )
        self.elapsed_label.setText(f"ELAPSED: {float(snapshot.get('elapsed_seconds', 0.0)):.1f} s")

    def _on_worker_completed(self, status, detail):
        self.timer.stop()
        self._tick_pending = False
        self._sync_library_metadata(detail)
        self.package_label.setText("PACKAGE: " + status)
        suffix = " / physical stop not inferred" if status in {"STOPPED", "INTERRUPTED", "FAULTED", "INCOMPLETE"} else ""
        self.status.setText(status + suffix + ((" / " + detail) if detail else ""))

    def _on_worker_thread_finished(self):
        self._worker = None
        self._thread = None
        self._set_running_controls(False)

    def stop_sweep(self):
        if self._worker is None:
            return
        self.timer.stop()
        self.status.setText("STOP REQUESTED")
        self.stop_requested.emit()

    def emergency_stop(self):
        if self._worker is None:
            return
        self.timer.stop()
        self.status.setText("EMERGENCY STOP REQUESTED")
        self.emergency_requested.emit()

    def record_observation(self):
        label = self.rotation_label.currentData()
        if label is None or self._worker is None:
            return
        self.observe_requested.emit(label)

    def _on_observation_result(self, ok, message):
        self.note.setText(message)

    def open_library(self):
        try:
            from ui.raw_log_database_manager import RawLogDatabaseManager
            self.library_window = RawLogDatabaseManager(self.owner)
            self.library_window.setAttribute(Qt.WA_DeleteOnClose, True)
            self.library_window.show()
            self.library_window.raise_()
            self.library_window.activateWindow()
        except Exception as exc:
            QMessageBox.critical(self, "RawLog Library", f"Libraryを開けません。\n{type(exc).__name__}: {exc}")

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
