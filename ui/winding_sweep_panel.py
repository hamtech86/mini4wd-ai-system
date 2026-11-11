"""Qt UI adapter for the production 310 protocol-v2 sequence."""
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import uuid

from PyQt5.QtCore import QObject, QThread, QTimer, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QComboBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QMessageBox,
    QPushButton, QVBoxLayout,
)

from measurement_310.engine import SequenceController, SequenceState
from measurement_310.evidence_bundle import write_evidence_bundle_manifest
from measurement_310.protocol_v1_session import TransportEvidenceJournal
from measurement_310.protocol_v2 import (
    DriveDirection, PROTOCOL_V2_MAGIC, PROTOCOL_V2_VERSION,
    ProtocolV2Codec, StopReason,
)
from measurement_310.protocol_v2_session import ProtocolV2HostSession
from measurement_310.transport import PySerialTransport
from raw_log_library.manager import RawLog, RawLogLibrary
from raw_log_v2.storage import RawLogV2Writer


class WindingSweepWorker(QObject):
    """All serial, protocol, sequence and RawLog work stays off the Qt UI thread."""

    started = pyqtSignal(bool, str)
    progress = pyqtSignal(dict)
    completed = pyqtSignal(str, str)
    observation_result = pyqtSignal(bool, str)

    def __init__(self, sequence, protocol_session, stop_reason_box, log_id, package_root):
        super().__init__()
        self.sequence = sequence
        self.protocol_session = protocol_session
        self.stop_reason_box = stop_reason_box
        self.log_id = log_id
        self.package_root = Path(package_root)
        self._completed = False
        self._operator_stop = False

    @pyqtSlot()
    def start(self):
        try:
            recovered = self.sequence.startup_recover()
            for item in recovered:
                recovered_id = item.get("log_id") if isinstance(item, dict) else None
                if not isinstance(recovered_id, str):
                    continue
                recovered_manifest = self.package_root / recovered_id / "manifest.json"
                if not recovered_manifest.is_file():
                    continue
                try:
                    manifest_body = json.loads(recovered_manifest.read_text(encoding="utf-8"))
                    recovered_session = manifest_body.get("measurement_session_id")
                    if not isinstance(recovered_session, str):
                        continue
                    evidence_path = (
                        self.package_root / ".transport-evidence" / recovered_session
                        / "transport-evidence-v1.jsonl"
                    )
                    if evidence_path.is_file():
                        journal = TransportEvidenceJournal(evidence_path)
                        write_evidence_bundle_manifest(
                            self.package_root / recovered_id, journal, recovered_session
                        )
                except Exception:
                    # Preserve the recovered package and persistent re-arm
                    # inhibition; never synthesize or downgrade Evidence.
                    pass
            self.sequence.start()
            state = self.sequence.state
            if state in {SequenceState.FAULT, SequenceState.ABORTED}:
                self.started.emit(False, self.sequence._last_fault or state.value)
                self._complete(self.sequence._last_fault or state.value)
                return
            self.started.emit(True, "")
        except Exception as exc:
            self.started.emit(False, f"{type(exc).__name__}: {exc}")
            self._complete(f"{type(exc).__name__}: {exc}")

    @pyqtSlot()
    def tick(self):
        if self._completed:
            return
        state = self.sequence.poll()
        stage_index = int(self.sequence.stage_index)
        elapsed = 0.0
        if self.sequence.stage_start_ns is not None:
            elapsed = max(0.0, (time.monotonic_ns() - self.sequence.stage_start_ns) / 1_000_000_000)
        self.progress.emit({
            "state": state.value,
            "stage_index": stage_index,
            "pwm": stage_index if stage_index >= 0 else None,
            "elapsed_seconds": elapsed,
            "boot_id64": getattr(self.protocol_session, "boot_id64", None),
        })
        if state in {SequenceState.COMPLETED, SequenceState.ABORTED, SequenceState.FAULT}:
            self._complete(self.sequence._last_fault or "")

    @pyqtSlot(str)
    def observe(self, label):
        if self._completed or self.sequence.state != SequenceState.RUNNING:
            self.observation_result.emit(False, "スイープ実行中のみ注釈を記録できます。")
            return
        if label == "ROTATION":
            event = "ROTATION_START_CONFIRMED"
        elif label == "NO_ROTATION":
            event = "ROTATION_NOT_OBSERVED_AT_STAGE"
        else:
            self.observation_result.emit(False, "UNKNOWNは注釈を追加せず、推測もしません。")
            return
        try:
            self.sequence.record_visual_event(
                event, "operator",
                datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            )
            self.observation_result.emit(True, "目視注釈をRawLog v2 EVENTとして保存しました。")
        except Exception as exc:
            self.observation_result.emit(False, f"{type(exc).__name__}: {exc}")

    @pyqtSlot()
    def stop(self):
        if self._completed:
            return
        self._operator_stop = True
        self.stop_reason_box["reason"] = StopReason.OPERATOR_REQUEST
        self.sequence.abort("user_stop")
        self._complete(self.sequence._last_fault or "")

    @pyqtSlot()
    def emergency_stop(self):
        if self._completed:
            return
        self._operator_stop = True
        self.stop_reason_box["reason"] = StopReason.OPERATOR_REQUEST
        self.sequence.abort("safety_stop")
        self._complete(self.sequence._last_fault or "")

    def _package_status(self):
        final_manifest = self.package_root / self.log_id / "manifest.json"
        work_dir = self.package_root / ".work" / self.log_id
        try:
            if final_manifest.is_file():
                return str(json.loads(final_manifest.read_text(encoding="utf-8")).get("status", "UNKNOWN"))
            if (work_dir / "records.jsonl").is_file() and (work_dir / "work_state.json").is_file():
                return "incomplete"
        except Exception:
            pass
        return "not_started"

    def _complete(self, detail):
        if self._completed:
            return
        self._completed = True
        try:
            self.protocol_session.flush_evidence()
        except Exception as exc:
            detail = (detail + "; " if detail else "") + f"Evidence flush: {type(exc).__name__}: {exc}"
        try:
            self.protocol_session.disconnect()
        except Exception as exc:
            detail = (detail + "; " if detail else "") + f"Transport disconnect: {type(exc).__name__}: {exc}"
        self.completed.emit(self._package_status(), detail)


class WindingSweepPanel(QGroupBox):
    """Qt timer queues sequence polls; it never performs serial I/O itself."""

    start_requested = pyqtSignal()
    tick_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    emergency_requested = pyqtSignal()
    observe_requested = pyqtSignal(str)

    def __init__(self, parent, root: Path, get_instance_id, get_breakin_controller):
        super().__init__("④ 巻線 PWM スイープ / Protocol v2")
        self.owner = parent
        self.root = Path(root)
        self.get_instance_id = get_instance_id
        self.get_breakin_controller = get_breakin_controller
        self.library = RawLogLibrary(self.root / "data" / "raw_logs")
        self.log_id = None
        self.measurement_session_id = None
        self.sequence = None
        self.protocol_session = None
        self._record_registered = False
        self._tick_pending = False
        self._thread = None
        self._worker = None
        self._session_started = False

        layout = QVBoxLayout(self)
        status = QGridLayout()
        self.status = QLabel("READY")
        self.log_label = QLabel("LOG: --")
        self.instance_label = QLabel("INSTANCE: --")
        self.stage_label = QLabel("PWM: -- / 30")
        self.elapsed_label = QLabel("ELAPSED: --")
        self.package_label = QLabel("PACKAGE: NOT CREATED")
        for row, (name, widget) in enumerate((
            ("STATUS", self.status), ("LOG", self.log_label),
            ("MOTOR INSTANCE", self.instance_label), ("STAGE", self.stage_label),
            ("ELAPSED", self.elapsed_label), ("RAWLOG", self.package_label),
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
        self.rotation_label.addItem("不明（記録しない）", "UNKNOWN")
        observation.addWidget(self.rotation_label, 1)
        self.note = QLabel("A0/A1/A4/A5は個別raw sampleとして記録。A0/A1平均や電流制限制御には使用しません。HARDWARE_CURRENT_LIMIT_CONFIRMED=falseは維持されます。")
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
        self.start_button.setEnabled(not running and not self._session_started)
        self.stop_button.setEnabled(running)
        self.observe_button.setEnabled(False)
        for name in ("start", "manager", "recipe", "motor_connect", "motor_disconnect", "motor_arm"):
            widget = getattr(self.owner, name, None)
            if widget is not None:
                widget.setEnabled(not running and not self._session_started)
        for name in ("stop", "emergency_stop_fixed"):
            widget = getattr(self.owner, name, None)
            if widget is not None:
                widget.setEnabled(True if name == "emergency_stop_fixed" else running)

    def _start_worker(self, start_args):
        self._thread = QThread(self)
        self._worker = WindingSweepWorker(
            self.sequence, self.protocol_session, start_args["stop_reason_box"],
            self.log_id, self.root / "data" / "raw_logs_v2",
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
        if self._worker is not None or self._thread is not None:
            return
        instance_id = self.get_instance_id()
        if instance_id is None:
            QMessageBox.warning(self, "Winding Sweep", "Motor Instanceを選択してください。")
            return
        breakin = self.get_breakin_controller()
        if breakin is None or getattr(breakin, "running", False):
            QMessageBox.warning(self, "Winding Sweep", "既存のBreak-in/Benchmark実行中、またはController不在のため開始できません。")
            return
        if getattr(self.owner, "_stop_latched", False):
            QMessageBox.warning(self, "Winding Sweep", "STOP latch中です。新しいアプリケーションセッションが必要です。")
            return
        if getattr(self.owner, "_arm_accepted", False):
            QMessageBox.warning(self, "Winding Sweep", "既存ASCII ARM状態を解除してから開始してください。")
            return

        legacy_serial = getattr(breakin, "serial", None)
        stop_check = getattr(legacy_serial, "_stop_requested", None)
        if callable(stop_check) and stop_check():
            QMessageBox.warning(self, "Winding Sweep", "既存SerialControllerにSTOP latchがあります。新しいアプリケーションセッションが必要です。")
            return
        confirmation = QMessageBox.question(
            self, "Driver Power Isolation",
            "USBシリアルを開くとArduinoがリセットされます。L298Nの12Vドライバー電源スイッチをOFFにしたことを確認してください。\n\nOFFにしてからProtocol v2セッションを開始しますか？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if confirmation != QMessageBox.Yes:
            return
        if legacy_serial is not None and getattr(legacy_serial, "connected", False):
            try:
                legacy_serial.disconnect()
            except Exception as exc:
                QMessageBox.critical(self, "Winding Sweep", f"既存UARTを解放できません。\n{type(exc).__name__}: {exc}")
                return

        port = getattr(legacy_serial, "serial_port", "/dev/ttyACM0")
        baudrate = int(getattr(legacy_serial, "baudrate", 57600))
        session_id = str(uuid.uuid4())
        acquired_at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        record = RawLog(
            device_type="MOTOR",
            device_model="MOTOR_BREAKIN_V3",
            firmware_version=None,
            device_instance_id=str(instance_id),
            motor_id=str(instance_id),
            measurement_session_id=session_id,
            acquired_at=acquired_at,
            measurement_condition="Protocol v2; FWD; PWM 0..30; 31 stages x 10 seconds; Python orchestrated",
            notes="Protocol v2 HELLO boot identity; firmware version/model is not returned by current HELLO_ACK. No DATA26 conversion.",
        )
        try:
            self.library.register_v2_reference(record)
            self.log_id = record.log_id
            self._record_registered = True
            self.measurement_session_id = session_id
            package_root = self.root / "data" / "raw_logs_v2"
            writer = RawLogV2Writer(package_root)
            transport = PySerialTransport(
                port, baudrate, timeout_s=0.0, write_timeout_s=0.10,
                startup_delay_s=2.0,
            )
            codec = ProtocolV2Codec(PROTOCOL_V2_MAGIC, PROTOCOL_V2_VERSION)
            self.protocol_session = ProtocolV2HostSession.for_rawlog_session(
                transport, codec, package_root, session_id,
            )
            stop_reason_box = {"reason": StopReason.INTERNAL_HOST_FAULT}

            def send_stop():
                reason = stop_reason_box["reason"]
                self.protocol_session.send_stop_best_effort(stop_reason=int(reason))

            def send_normal_stop():
                self.protocol_session.send_stop_best_effort(
                    stop_reason=int(StopReason.NORMAL_COMPLETION)
                )

            manifest_fields = {
                "log_id": self.log_id,
                "measurement_session_id": session_id,
                "motor_instance_id": str(instance_id),
                "device": {
                    "type": "MOTOR", "model": None, "firmware_version": None,
                    "firmware_build": None, "firmware_id": None,
                    "adc_resolution_bits": 10,
                },
                "measurement_conditions": {
                    "direction": "FWD", "voltage_control_mode": "UNKNOWN",
                    "sweep_pwm_min": 0, "sweep_pwm_max": 30,
                    "stage_duration_ms": 10000, "schedule_owner": "PYTHON",
                },
            }
            self.sequence = SequenceController.with_protocol_session(
                writer, manifest_fields, self.protocol_session,
                send_stop=send_stop, send_normal_stop=send_normal_stop,
                stage_direction=lambda _index: int(DriveDirection.FWD),
            )
            self.log_label.setText("LOG: " + self.log_id)
            self.instance_label.setText("INSTANCE: " + str(instance_id))
            self.rotation_label.setCurrentIndex(0)
            self.status.setText("STARTING / V2 HELLO")
            self.package_label.setText("PACKAGE: STARTING")
            self._set_running_controls(True)
            self._start_worker({"stop_reason_box": stop_reason_box})
            if hasattr(self.owner, "motor_serial_status"):
                self.owner.motor_serial_status.setText("MOTOR: PROTOCOL V2 SESSION STARTING")
        except Exception as exc:
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
            self.status.setText("RUNNING / PROTOCOL V2")
            self.package_label.setText("PACKAGE: INCOMPLETE (RECORDING)")
            self.timer.start()
        else:
            self.status.setText("START FAILED / " + (detail or "UNKNOWN"))
            self.timer.stop()

    def _queue_tick(self):
        if self._tick_pending or self._worker is None:
            return
        self._tick_pending = True
        self.tick_requested.emit()

    def _on_progress(self, snapshot):
        self._tick_pending = False
        self.status.setText(str(snapshot.get("state", "UNKNOWN")).upper())
        stage_index = snapshot.get("stage_index", -1)
        pwm = snapshot.get("pwm")
        self.stage_label.setText(
            f"PWM: {pwm if pwm is not None else '--'} / 30  ({int(stage_index) + 1}/31)"
        )
        self.elapsed_label.setText(f"ELAPSED: {float(snapshot.get('elapsed_seconds', 0.0)):.1f} s")
        boot_id = snapshot.get("boot_id64")
        if boot_id:
            self.package_label.setText(f"PACKAGE: RECORDING / BOOT {int(boot_id):016X}")

    def _on_worker_completed(self, status, detail):
        self.timer.stop()
        self._tick_pending = False
        self._sync_library_metadata(detail)
        self.package_label.setText("PACKAGE: " + status.upper())
        suffix = " / physical motor state not inferred"
        self.status.setText(status.upper() + suffix + ((" / " + detail) if detail else ""))

    def _on_worker_thread_finished(self):
        self._worker = None
        self._thread = None
        self._session_started = True
        self._set_running_controls(False)
        if hasattr(self.owner, "_stop_latched"):
            self.owner._stop_latched = True
        if hasattr(self.owner, "_arm_accepted"):
            self.owner._arm_accepted = False
        if hasattr(self.owner, "motor_arm"):
            self.owner.motor_arm.setEnabled(False)
        if hasattr(self.owner, "motor_connect"):
            self.owner.motor_connect.setEnabled(False)
        if hasattr(self.owner, "motor_disconnect"):
            self.owner.motor_disconnect.setEnabled(False)
        if hasattr(self.owner, "motor_serial_status"):
            self.owner.motor_serial_status.setText(
                "MOTOR: V2 SESSION ENDED / RESTART REQUIRED; DRIVER SUPPLY OFF BEFORE NEXT SESSION"
            )
        self.start_button.setEnabled(False)

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
            return "not_created"
        root = self.root / "data" / "raw_logs_v2"
        manifest = root / self.log_id / "manifest.json"
        work = root / ".work" / self.log_id / "work_state.json"
        try:
            if manifest.is_file():
                return str(json.loads(manifest.read_text(encoding="utf-8")).get("status", "unknown"))
            if work.is_file():
                return "incomplete"
        except Exception:
            pass
        return "not_started"

    def _sync_library_metadata(self, extra_note=""):
        if not self.log_id or not self._record_registered:
            return
        status = self._manifest_status()
        note = f"Protocol v2 RawLog status={status}"
        if extra_note:
            note += "; " + extra_note
        self.library.update_metadata(self.log_id, notes=note)
