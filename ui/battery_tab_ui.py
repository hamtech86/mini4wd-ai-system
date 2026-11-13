"""Integrated Battery operation tab.

Battery measurements remain in memory until a channel reports COMPLETE and the
operator explicitly registers the result. STOP/ERROR/CANCEL results are never
registered as benchmark results.
"""
import sqlite3
import uuid
from datetime import datetime
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel, QPushButton, QComboBox, QTabWidget, QScrollArea, QMessageBox
from battery_system.serial import BatterySerial
from raw_log_library import RawLog, RawLogLibrary
from ui.battery_database_ui import BatteryDatabaseDialog
from database.path_resolver import connect_database, resolve_database_path


class BatteryTab(QWidget):
    def __init__(self, db_path=None, transport=None, parent=None, database_available=None, raw_log_library=None):
        super().__init__(parent)
        if database_available is None:
            try:
                db_path = resolve_database_path(db_path, required_tables=("battery_model", "battery_instance", "battery_benchmark_result"))
                database_available = True
            except Exception:
                database_available = False
        self.database_available = bool(database_available)
        self.anonymous_mode = not self.database_available
        self.db_path = str(resolve_database_path(db_path, required_tables=("battery_model", "battery_instance", "battery_benchmark_result"))) if self.database_available else None
        self.transport = transport or BatterySerial()
        self.raw_log_library = raw_log_library or RawLogLibrary()
        self.samples = {1: [], 2: []}
        self.latest_status = {1: "IDLE", 2: "IDLE"}
        self.session_started = {1: None, 2: None}
        self.completed = {1: False, 2: False}
        self._raw_capture = {1: [], 2: []}
        self._capture_active = {1: False, 2: False}
        self._capture_terminal_status = {1: None, 2: None}
        self.local_raw_log_ids = {1: None, 2: None}
        self._build()
        self._load_models_and_instances()
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.poll_serial)
        self._set_controls_enabled(False)

    def _db(self):
        return connect_database(self.db_path)

    def _build(self):
        root = QVBoxLayout(self)
        tabs = QTabWidget()
        operation = QWidget()
        op = QVBoxLayout(operation)

        status = QGroupBox("STATUS")
        sg = QGridLayout(status)
        self.status_labels = {}
        for col, ch in enumerate(("ALL", "CH1", "CH2")):
            self.status_labels[ch] = QLabel(f"{ch}: IDLE")
            sg.addWidget(self.status_labels[ch], 0, col)
        op.addWidget(status)

        assignment = QGroupBox("BATTERY INSTANCE ASSIGNMENT")
        ar = QVBoxLayout(assignment)
        mr = QHBoxLayout()
        self.model = QComboBox()
        mr.addWidget(QLabel("Battery Model"))
        mr.addWidget(self.model)
        ar.addLayout(mr)
        ir = QHBoxLayout()
        self.ch1_instance = QComboBox()
        self.ch2_instance = QComboBox()
        ir.addWidget(QLabel("CH1 Instance"))
        ir.addWidget(self.ch1_instance)
        ir.addWidget(QLabel("CH2 Instance"))
        ir.addWidget(self.ch2_instance)
        ar.addLayout(ir)
        self.assignment_status = QLabel("Battery Model / Instanceを読み込み中...")
        ar.addWidget(self.assignment_status)
        op.addWidget(assignment)

        controls = QGroupBox("5A DISCHARGE")
        cr = QGridLayout(controls)
        for col, name in enumerate(("ALL", "CH1", "CH2")):
            cr.addWidget(QLabel(name), 0, col)
        self.all_start = QPushButton("START")
        self.ch1_start = QPushButton("START")
        self.ch2_start = QPushButton("START")
        self.all_stop = QPushButton("STOP")
        self.ch1_stop = QPushButton("STOP")
        self.ch2_stop = QPushButton("STOP")
        for col, b in enumerate((self.all_start, self.ch1_start, self.ch2_start)):
            cr.addWidget(b, 1, col)
        for col, b in enumerate((self.all_stop, self.ch1_stop, self.ch2_stop)):
            cr.addWidget(b, 2, col)
        self.all_start.clicked.connect(lambda: self.start_channel(None))
        self.ch1_start.clicked.connect(lambda: self.start_channel(1))
        self.ch2_start.clicked.connect(lambda: self.start_channel(2))
        self.all_stop.clicked.connect(lambda: self.stop_channel(None))
        self.ch1_stop.clicked.connect(lambda: self.stop_channel(1))
        self.ch2_stop.clicked.connect(lambda: self.stop_channel(2))
        op.addWidget(controls)

        live = QGroupBox("LIVE DATA")
        grid = QGridLayout(live)
        self.live_labels = {}
        fields = (("CH1", "Voltage"), ("CH1", "Current"), ("CH1", "PWM"), ("CH1", "Time"),
                  ("CH2", "Voltage"), ("CH2", "Current"), ("CH2", "PWM"), ("CH2", "Time"))
        for i, (ch, f) in enumerate(fields):
            self.live_labels[(ch, f)] = QLabel(f"{ch} {f}: --")
            grid.addWidget(self.live_labels[(ch, f)], i // 4, i % 4)
        op.addWidget(live)

        result = QGroupBox("RESULT / MANUAL REGISTRATION")
        rr = QGridLayout(result)
        self.result_labels = {}
        for row, ch in enumerate(("CH1", "CH2")):
            self.result_labels[ch] = QLabel(f"{ch} Result: no completed measurement")
            rr.addWidget(self.result_labels[ch], row, 0, 1, 2)
        self.register_result_button = QPushButton("REGISTER RESULT TO DATABASE")
        self.register_result_button.setEnabled(False)
        self.register_result_button.clicked.connect(self.register_results)
        rr.addWidget(self.register_result_button, 2, 0, 1, 2)
        self.retry_raw_log_button = QPushButton("RETRY LOCAL RAWLOG SAVE")
        self.retry_raw_log_button.setEnabled(False)
        self.retry_raw_log_button.clicked.connect(self.retry_anonymous_raw_log_saves)
        rr.addWidget(self.retry_raw_log_button, 3, 0, 1, 2)
        op.addWidget(result)
        op.addWidget(QLabel("正常終了(COMPLETE)した測定だけを、確認後に手動登録します。STOP/ERROR/CANCELはDB登録しません。"))
        # The integrated MainUI reserves substantial vertical space for device
        # connection and global logs. Keep the complete Battery operation page
        # intact, but make it scrollable so START/STOP controls are reachable on
        # smaller screens instead of being clipped below the tab viewport.
        self.operation_scroll_area = QScrollArea()
        self.operation_scroll_area.setWidgetResizable(True)
        self.operation_scroll_area.setWidget(operation)
        tabs.addTab(self.operation_scroll_area, "5A DISCHARGE")

        db_page = QWidget()
        db_layout = QVBoxLayout(db_page)
        db_button = QPushButton("OPEN BATTERY INSTANCE / RESULT DATABASE")
        db_button.clicked.connect(self.open_database)
        db_layout.addWidget(db_button)
        db_layout.addStretch(1)
        tabs.addTab(db_page, "DATABASE")
        tabs.setTabEnabled(1, self.database_available)
        if self.anonymous_mode:
            self.register_result_button.setText("LOCAL RAWLOG ONLY / ANONYMOUS MODE")
            self.register_result_button.setEnabled(False)
        root.addWidget(tabs)

    def _load_models_and_instances(self):
        self.model.clear()
        self.ch1_instance.clear()
        self.ch2_instance.clear()
        if self.anonymous_mode:
            self.model.addItem("ANONYMOUS / NO DATABASE MODEL", None)
            self.ch1_instance.addItem("ANONYMOUS / NO INSTANCE", None)
            self.ch2_instance.addItem("ANONYMOUS / NO INSTANCE", None)
            self.model.setEnabled(False)
            self.ch1_instance.setEnabled(False)
            self.ch2_instance.setEnabled(False)
            self.assignment_status.setText("ANONYMOUS MODE: Instance assignment and database lookup are disabled. Measurements are saved to the local RawLog library.")
            return
        try:
            with self._db() as db:
                models = db.execute("SELECT battery_model_id,model_code,name FROM battery_model WHERE COALESCE(is_deleted,0)=0 ORDER BY model_code").fetchall()
                instances = db.execute("SELECT bi.instance_id,bi.battery_model_id,bi.nickname,bm.model_code FROM battery_instance bi LEFT JOIN battery_model bm ON bm.battery_model_id=bi.battery_model_id WHERE COALESCE(bi.is_deleted,0)=0 ORDER BY bi.instance_id").fetchall()
            for mid, code, name in models:
                self.model.addItem(f"{code} / {name}", mid)
            for iid, mid, nickname, code in instances:
                text = f"{iid} / {nickname or code or ''}".rstrip(" /")
                self.ch1_instance.addItem(text, iid)
                self.ch2_instance.addItem(text, iid)
            self.assignment_status.setText("Battery Modelを選択し、CH1 / CH2 Instanceを指定してください" if models and instances else "Battery Model / InstanceをDATABASEから登録してください")
        except sqlite3.Error as exc:
            self.assignment_status.setText("Battery Model / Instanceを読み込めません")
            QMessageBox.warning(self, "Battery", f"Battery Model / Instanceを読み込めません。\n{exc}")

    def _set_controls_enabled(self, enabled):
        have1 = self.ch1_instance.currentData() is not None
        have2 = self.ch2_instance.currentData() is not None
        if self.anonymous_mode:
            for b in (self.ch1_start, self.ch1_stop, self.ch2_start, self.ch2_stop):
                b.setEnabled(enabled)
            self.all_start.setEnabled(enabled)
            self.all_stop.setEnabled(enabled)
            return
        for b in (self.ch1_start, self.ch1_stop, self.ch2_start, self.ch2_stop):
            b.setEnabled(enabled and have1 and have2)
        self.all_start.setEnabled(enabled and have1 and have2)
        self.all_stop.setEnabled(enabled)

    def set_connected(self, connected):
        self._set_controls_enabled(connected)
        if connected:
            self.timer.start()
        else:
            self.timer.stop()
            if self.anonymous_mode:
                for ch in (1, 2):
                    if self._capture_active[ch]:
                        terminal = self._capture_terminal_status[ch] or "DISCONNECTED_INCOMPLETE"
                        self._finalize_anonymous_raw_log(ch, terminal)

    def _status(self, ch, value):
        value = str(value).strip().upper()
        self.latest_status[ch] = value
        self.status_labels[f"CH{ch}"].setText(f"CH{ch}: {value}")
        self.status_labels["ALL"].setText(f"ALL: {self.latest_status[1]} / {self.latest_status[2]}")
        if value == "COMPLETE":
            self.completed[ch] = True
            self.result_labels[f"CH{ch}"].setText(f"CH{ch} Result: COMPLETE / {len(self.samples[ch])} samples")
        elif value in ("STOPPED", "STOP", "CANCEL", "CANCELLED", "ERROR"):
            self.completed[ch] = False
            self.result_labels[f"CH{ch}"].setText(f"CH{ch} Result: {value} / DB登録不可")
        if self.anonymous_mode and value in ("COMPLETE", "STOPPED", "STOP", "CANCEL", "CANCELLED", "ERROR"):
            self._finalize_anonymous_raw_log(ch, value)
        self._update_register_button()

    def _update_register_button(self):
        self.register_result_button.setEnabled(
            self.database_available and any(self.completed[ch] and self.samples[ch] for ch in (1, 2))
        )

    def _finalize_anonymous_raw_log(self, channel, terminal_status):
        if not self.anonymous_mode or not self._capture_active[channel]:
            return None
        body = "".join(self._raw_capture[channel])
        self._capture_terminal_status[channel] = terminal_status
        if not body:
            self._capture_active[channel] = False
            self._capture_terminal_status[channel] = None
            self.retry_raw_log_button.setEnabled(any(
                self._capture_active[ch] and self._capture_terminal_status[ch] for ch in (1, 2)
            ))
            return None
        started = self.session_started[channel] or datetime.now().isoformat(timespec="seconds")
        record = RawLog(
            device_type="BATTERY",
            device_model="BATTERY_5A",
            device_instance_id=None,
            channel=f"CH{channel}",
            battery_id=None,
            measurement_session_id=None,
            acquired_at=started,
            measurement_condition="ANONYMOUS_5A_DISCHARGE",
            notes=f"anonymous=true; terminal_status={terminal_status}; sample_count={len(self.samples[channel])}",
        )
        try:
            path = self.raw_log_library.register(record, body)
            self._capture_active[channel] = False
            self._capture_terminal_status[channel] = None
            self.local_raw_log_ids[channel] = record.log_id
            self.result_labels[f"CH{channel}"].setText(
                f"CH{channel} Result: {terminal_status} / LOCAL RAWLOG {record.log_id}"
            )
            self.retry_raw_log_button.setEnabled(any(
                self._capture_active[ch] and self._capture_terminal_status[ch] for ch in (1, 2)
            ))
            return path
        except Exception as exc:
            # Keep the exact capture active and retryable. A transient filesystem
            # or index error must not discard the only copy of the received data.
            self.retry_raw_log_button.setEnabled(True)
            self.result_labels[f"CH{channel}"].setText(
                f"CH{channel} Result: RAWLOG SAVE FAILED / RETRY AVAILABLE / {type(exc).__name__}: {exc}"
            )
            return None

    def retry_anonymous_raw_log_saves(self):
        if not self.anonymous_mode:
            return
        for ch in (1, 2):
            terminal_status = self._capture_terminal_status[ch]
            if self._capture_active[ch] and terminal_status:
                self._finalize_anonymous_raw_log(ch, terminal_status)
        self.retry_raw_log_button.setEnabled(any(
            self._capture_active[ch] and self._capture_terminal_status[ch] for ch in (1, 2)
        ))

    def _same_instance_conflict(self, channel):
        a = self.ch1_instance.currentData()
        b = self.ch2_instance.currentData()
        if a is None or b is None or a != b:
            return False
        if channel is None:
            return True
        other = 2 if channel == 1 else 1
        return self.latest_status[other] not in ("IDLE", "STOPPED", "DISCONNECTED", "COMPLETE", "ERROR", "CANCEL", "CANCELLED")

    def start_channel(self, channel):
        if not self.transport.connected:
            return
        a = self.ch1_instance.currentData()
        b = self.ch2_instance.currentData()
        if self.anonymous_mode and any(
            self._capture_active[ch] and self._capture_terminal_status[ch]
            for ch in ((1, 2) if channel is None else (channel,))
        ):
            self.retry_anonymous_raw_log_saves()
            if any(
                self._capture_active[ch] and self._capture_terminal_status[ch]
                for ch in ((1, 2) if channel is None else (channel,))
            ):
                QMessageBox.warning(self, "Battery RawLog", "前回のRawLog保存が未完了です。保存を再試行してから放電を開始してください。")
                return
        if not self.anonymous_mode and (a is None or b is None):
            QMessageBox.warning(self, "Battery Instance", "CH1 / CH2のBattery Instanceを指定してください。")
            return
        if not self.anonymous_mode and self._same_instance_conflict(channel):
            QMessageBox.warning(self, "Battery Instance Conflict", f"CH1: {a}\nCH2: {b}\n\n同じBattery Instanceを同時に使用することはできません。\nInstanceを変更してください。")
            return
        if channel is None:
            targets = (1, 2)
        else:
            targets = (channel,)
        now = datetime.now().isoformat(timespec="seconds")
        for ch in targets:
            self.session_started[ch] = now
            self.samples[ch] = []
            self.completed[ch] = False
        if not self.transport.start(channel):
            QMessageBox.warning(self, "Battery", "STARTコマンドを送信できませんでした。")
            return
        if self.anonymous_mode:
            for ch in targets:
                self._raw_capture[ch] = []
                self._capture_active[ch] = True
                self.local_raw_log_ids[ch] = None
        for ch in targets:
            self._status(ch, "STARTING")
        self._update_register_button()

    def stop_channel(self, channel):
        if not self.transport.connected:
            return
        if not self.transport.stop(channel):
            QMessageBox.warning(self, "Battery", "STOPコマンドを送信できませんでした。")
            return
        targets = (1, 2) if channel is None else (channel,)
        for ch in targets:
            self._status(ch, "STOPPING")

    def poll_serial(self):
        for line in self.transport.read_lines():
            raw_line = line
            text = line.strip()
            if text.startswith("STATUS"):
                if self.anonymous_mode:
                    for ch in (1, 2):
                        if self._capture_active[ch]:
                            self._raw_capture[ch].append(raw_line)
                parts = text.split(',')
                if len(parts) >= 3:
                    self._status(1, parts[1])
                    self._status(2, parts[2])
                continue
            sample = self.transport.parse_data(text)
            if sample is None:
                # Preserve malformed DATA frames too. If the channel field is
                # still readable, attach the exact line to that channel;
                # otherwise retain it in every active channel capture.
                if self.anonymous_mode and text.startswith("DATA,"):
                    parts = text.split(",")
                    try:
                        raw_channel = int(parts[2].strip().upper().replace("CH", ""))
                    except (IndexError, TypeError, ValueError):
                        raw_channel = None
                    targets = (raw_channel,) if raw_channel in (1, 2) else (1, 2)
                    for target in targets:
                        if self._capture_active[target]:
                            self._raw_capture[target].append(raw_line)
                continue
            ch = sample.channel
            if ch not in self.samples:
                if self.anonymous_mode:
                    for target in (1, 2):
                        if self._capture_active[target]:
                            self._raw_capture[target].append(raw_line)
                continue
            if self.anonymous_mode and self._capture_active[ch]:
                self._raw_capture[ch].append(raw_line)
            prefix = f"CH{ch}"
            self.samples[ch].append(sample)
            self.live_labels[(prefix, "Voltage")].setText(f"{prefix} Voltage: {sample.voltage:.3f} V")
            self.live_labels[(prefix, "Current")].setText(f"{prefix} Current: {sample.current:.3f} A")
            self.live_labels[(prefix, "PWM")].setText(f"{prefix} PWM: {sample.pwm}")
            self.live_labels[(prefix, "Time")].setText(f"{prefix} Time: {sample.elapsed_sec:.1f} s")
            if str(sample.state).strip().upper() == "COMPLETE":
                self._status(ch, "COMPLETE")
            elif str(sample.state).strip().upper() in ("ERROR", "CANCEL", "CANCELLED", "STOPPED"):
                self._status(ch, sample.state)
            else:
                self.result_labels[prefix].setText(f"{prefix} Result: {len(self.samples[ch])} samples / latest {sample.voltage:.3f} V, {sample.current:.3f} A")

    @staticmethod
    def _stats(samples):
        samples = sorted(samples, key=lambda x: x.elapsed_sec)
        n = len(samples)
        avg_v = sum(x.voltage for x in samples) / n
        avg_i = sum(x.current for x in samples) / n
        powers = [x.voltage * x.current for x in samples]
        avg_p = sum(powers) / n
        max_i = max(x.current for x in samples)
        max_p = max(powers)
        duration = max(x.elapsed_sec for x in samples) - min(x.elapsed_sec for x in samples)
        cap = 0.0
        energy = 0.0
        for a, b in zip(samples, samples[1:]):
            dt = max(0.0, b.elapsed_sec - a.elapsed_sec) / 3600.0
            cap += (a.current + b.current) * 0.5 * dt * 1000.0
            energy += (a.voltage * a.current + b.voltage * b.current) * 0.5 * dt
        return n, avg_v, avg_i, avg_p, max_i, max_p, duration, cap, energy

    @staticmethod
    def _table_columns(db, table):
        return {row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}

    @staticmethod
    def _insert_available(db, table, values):
        cols = BatteryTab._table_columns(db, table)
        data = {k: v for k, v in values.items() if k in cols}
        if not data:
            raise sqlite3.OperationalError(f"No compatible columns for {table}")
        names = ",".join(data.keys())
        marks = ",".join("?" for _ in data)
        db.execute(f"INSERT INTO {table}({names}) VALUES({marks})", tuple(data.values()))

    def register_results(self):
        if not self.database_available or not self.db_path:
            QMessageBox.information(self, "Anonymous Mode", "Database registration is unavailable. The original local RawLog is retained instead.")
            return
        completed = []
        for ch in (1, 2):
            if not self.completed[ch]:
                continue
            iid = self.ch1_instance.currentData() if ch == 1 else self.ch2_instance.currentData()
            if self.samples[ch] and iid:
                completed.append((ch, iid, self._stats(self.samples[ch])))
        if not completed:
            QMessageBox.warning(self, "Battery Result", "正常終了(COMPLETE)した測定がありません。")
            return
        if QMessageBox.question(self, "Battery Result", "COMPLETEした放電結果を確認しました。データベースへ登録しますか?", QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            with self._db() as db:
                for ch, iid, stats in completed:
                    n, av, ai, ap, mi, mp, dur, cap, energy = stats
                    sid = int(uuid.uuid4().int % 2147483647)
                    start = self.session_started[ch] or datetime.now().isoformat(timespec="seconds")
                    end = datetime.now().isoformat(timespec="seconds")
                    self._insert_available(db, "measurement_session", {
                        "session_id": sid, "instance_id": iid, "device_type": "EVALUATION",
                        "device_model": "BATTERY_5A", "firmware_version": "UNKNOWN",
                        "start_datetime": start, "end_datetime": end, "operator": "USER",
                        "result": "COMPLETE", "notes": f"Integrated Battery UI CH{ch}; manual result registration"
                    })
                    for s in self.samples[ch]:
                        self._insert_available(db, "measurement", {
                            "session_id": sid, "record_type": "BATTERY_5A", "device_model": "BATTERY_5A",
                            "instance_id": iid, "elapsed_time": s.elapsed_sec, "voltage1": s.voltage,
                            "current1": s.current, "pwm": s.pwm, "state": "COMPLETE", "power": s.voltage * s.current
                        })
                    self._insert_available(db, "battery_benchmark_result", {
                        "session_id": sid, "instance_id": iid, "analysis_version": "battery-benchmark-v1",
                        "measurement_count": n, "avg_voltage": av, "avg_current": ai, "avg_power": ap,
                        "max_current": mi, "max_power": mp, "discharge_time_s": dur,
                        "capacity_mah": cap, "energy_wh": energy
                    })
                db.commit()
            QMessageBox.information(self, "Battery Result", "COMPLETEしたMeasurementとBenchmark Resultを登録しました。")
            for ch, _, _ in completed:
                self.completed[ch] = False
                self.result_labels[f"CH{ch}"].setText(f"CH{ch} Result: REGISTERED")
            self._update_register_button()
        except sqlite3.Error as exc:
            QMessageBox.critical(self, "Battery Result", f"登録できません。\n{exc}")

    def open_database(self):
        if not self.database_available or not self.db_path:
            QMessageBox.information(self, "Anonymous Mode", "Battery database functions are unavailable in Anonymous Mode.")
            return
        dialog = BatteryDatabaseDialog(self.db_path, self)
        dialog.exec_()
        self._load_models_and_instances()
