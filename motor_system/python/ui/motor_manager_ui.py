"""Motor Instance Manager.

Instance is the navigation root:
    Instance -> Measurement Session -> selected Raw Logs -> Note/Result

History selection and GitHub registration are intentionally independent.
No measurement/session/raw body is deleted or rewritten by this manager.
"""
from __future__ import annotations

import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QApplication, QComboBox, QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget, QDialog, QInputDialog,
)

ROOT = Path(__file__).resolve().parents[3]
sys.path.append(str(ROOT))

from database.manager.database_manager import DatabaseManager
from database.repository.motor_instance_repository import MotorInstanceRepository
from database.repository.motor_repository import MotorRepository
from raw_log_library import RawLogLibrary
from raw_log_library.github_export import GitHubRawLogExporter, GitHubRegistrationError
from ui.instance_visibility import InstanceVisibilityStore


class MotorManagerUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Motor Instance Manager")
        self.resize(1400, 850)
        self.db = DatabaseManager(str(ROOT / "database" / "mini4wd.db"))
        self.db.connect()
        self.instance_repo = MotorInstanceRepository(self.db)
        self.motor_repo = MotorRepository(self.db)
        self.raw_library = RawLogLibrary(ROOT / "data" / "raw_logs")
        self.visibility = InstanceVisibilityStore()
        self.current_instance_id = None
        self.current_log_id = None
        self.sort_column = 0
        self.sort_ascending = False
        self.setup_ui()
        self.load_models()
        self.load_statuses()
        self.load_instances()

    def setup_ui(self):
        root = QVBoxLayout(self)
        header = QHBoxLayout()
        title = QLabel("Motor Instance Manager")
        title.setStyleSheet("font-size:20px;font-weight:bold;")
        header.addWidget(title); header.addStretch()
        refresh = QPushButton("Refresh"); refresh.clicked.connect(self.refresh_all)
        header.addWidget(refresh)
        root.addLayout(header)

        filters = QGroupBox("Instance Search / Filter")
        f = QHBoxLayout(filters)
        self.search = QLineEdit(); self.search.setPlaceholderText("Instance ID / Nickname")
        self.search.textChanged.connect(self.load_instances)
        f.addWidget(self.search)
        self.model_filter = QComboBox(); self.model_filter.addItem("Model: ALL", None)
        self.model_filter.currentIndexChanged.connect(self.load_instances); f.addWidget(self.model_filter)
        self.status_filter = QComboBox(); self.status_filter.addItem("Status: ALL", None)
        self.status_filter.currentIndexChanged.connect(self.load_instances); f.addWidget(self.status_filter)
        self.visibility_filter = QComboBox()
        self.visibility_filter.addItems(["Visibility: VISIBLE", "Visibility: HIDDEN", "Visibility: ALL"])
        self.visibility_filter.currentIndexChanged.connect(self.load_instances); f.addWidget(self.visibility_filter)
        root.addWidget(filters)

        self.instance_table = QTableWidget(0, 9)
        self.instance_table.setHorizontalHeaderLabels(
            ["Instance ID","Motor Model","Nickname","Status","Visibility","Session Count","RawLog Count","Created","Updated"]
        )
        self.instance_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.instance_table.setSelectionMode(QTableWidget.SingleSelection)
        self.instance_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.instance_table.cellDoubleClicked.connect(self.open_selected_instance)
        self.instance_table.horizontalHeader().sectionClicked.connect(self.sort_instances)
        root.addWidget(self.instance_table, 2)

        buttons = QHBoxLayout()
        for text, slot in [
            ("Open Detail / History", self.open_current_detail),
            ("New Instance", self.clear_form),
            ("Save Instance", self.save_instance),
            ("Set VISIBLE", lambda: self.set_visibility("VISIBLE")),
            ("Set HIDDEN", lambda: self.set_visibility("HIDDEN")),
        ]:
            b=QPushButton(text); b.clicked.connect(slot); buttons.addWidget(b)
        buttons.addStretch(); root.addLayout(buttons)

        self.detail = QWidget()
        d = QVBoxLayout(self.detail)
        self.detail_title = QLabel("No instance selected")
        self.detail_title.setStyleSheet("font-size:18px;font-weight:bold;")
        d.addWidget(self.detail_title)

        form_box=QGroupBox("Instance Information"); form=QGridLayout(form_box)
        self.model_box=QComboBox(); form.addWidget(QLabel("Motor Model"),0,0); form.addWidget(self.model_box,0,1)
        self.serial_edit=QLineEdit(); form.addWidget(QLabel("Serial Number"),0,2); form.addWidget(self.serial_edit,0,3)
        self.nickname_edit=QLineEdit(); form.addWidget(QLabel("Nickname"),1,0); form.addWidget(self.nickname_edit,1,1)
        self.status_box=QComboBox(); form.addWidget(QLabel("Status"),1,2); form.addWidget(self.status_box,1,3)
        form.setColumnStretch(1,1); form.setColumnStretch(3,1)
        d.addWidget(form_box)

        d.addWidget(QLabel("RawLog / History — all Instance-linked Raw Logs are shown; History is user-registered"))
        self.history_table=QTableWidget(0,9)
        self.history_table.setHorizontalHeaderLabels(
            ["Session","Date","Type","Note","RawLog","History","GitHub","Integrity","Result"]
        )
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        d.addWidget(self.history_table,2)

        actions=QHBoxLayout()
        for text,slot in [
            ("Register History",self.register_history),
            ("Remove from History",self.remove_history),
            ("Edit Note",self.edit_note),
            ("GitHub Register",self.register_github),
            ("Relink RawLog",self.relink_raw_log),
            ("View Raw Body",self.view_raw_body),
        ]:
            b=QPushButton(text); b.clicked.connect(slot); actions.addWidget(b)
        actions.addStretch(); d.addLayout(actions)
        root.addWidget(self.detail, 3)

    def load_models(self):
        self.model_box.clear(); self.model_filter.clear()
        self.model_filter.addItem("Model: ALL", None)
        for m in self.motor_repo.get_all():
            mid=m.get("motor_model_id")
            label=m.get("name") or str(mid)
            code=m.get("model_code") or m.get("series")
            label=f"{label} ({code})" if code else label
            self.model_box.addItem(label,mid); self.model_filter.addItem(label,mid)

    def load_statuses(self):
        self.status_box.clear(); self.status_filter.clear(); self.status_filter.addItem("Status: ALL",None)
        try:
            rows=self.db.execute("SELECT DISTINCT status FROM motor_instance WHERE status IS NOT NULL ORDER BY status").fetchall()
            statuses=[str(r[0]) for r in rows if r[0] is not None]
        except Exception:
            statuses=[]
        for s in statuses: self.status_box.addItem(s); self.status_filter.addItem(s,s)
        if self.status_box.count()==0: self.status_box.addItem("NEW")

    def _visibility_mode(self):
        return self.visibility_filter.currentText().split(": ",1)[-1].upper()

    def _all_instances(self):
        return list(self.instance_repo.get_list_view())

    def load_instances(self):
        try: rows=self._all_instances()
        except Exception as exc:
            self.instance_table.setRowCount(0); return
        mode=self._visibility_mode()
        search=self.search.text().strip().lower()
        model_id=self.model_filter.currentData(); status=self.status_filter.currentData()
        filtered=[]
        for row in rows:
            iid=str(row.get("instance_id",""))
            if mode!="ALL" and self.visibility.get(iid)!=mode: continue
            if model_id is not None and row.get("motor_model_id")!=model_id: continue
            if status is not None and row.get("status")!=status: continue
            hay=f"{iid} {row.get('nickname') or ''}".lower()
            if search and search not in hay: continue
            sessions=self.instance_repo.get_sessions(iid)
            logs=[x for x in self.raw_library.list_logs("MOTOR") if str(x.device_instance_id)==iid]
            row=dict(row); row["_sessions"]=len(sessions); row["_logs"]=len(logs)
            row["_visibility"]=self.visibility.get(iid); filtered.append(row)
        keymap=[lambda r:str(r.get("instance_id","")),lambda r:str(r.get("model_code") or r.get("motor_name") or ""),
                lambda r:str(r.get("nickname") or ""),lambda r:str(r.get("status") or ""),
                lambda r:r.get("_visibility",""),lambda r:r.get("_sessions",0),lambda r:r.get("_logs",0),
                lambda r:str(r.get("created_at") or ""),lambda r:str(r.get("updated_at") or "")]
        key=keymap[min(self.sort_column,len(keymap)-1)]
        try: filtered.sort(key=key,reverse=not self.sort_ascending)
        except TypeError: pass
        self.instance_table.setRowCount(len(filtered))
        for r,row in enumerate(filtered):
            model=row.get("motor_name") or row.get("motor_model_id") or ""
            code=row.get("model_code") or row.get("series")
            model=f"{model} ({code})" if code else str(model)
            vals=[row.get("instance_id"),model,row.get("nickname") or "",row.get("status") or "",
                  row.get("_visibility"),row.get("_sessions"),row.get("_logs"),row.get("created_at") or "",row.get("updated_at") or ""]
            for c,v in enumerate(vals):
                item=QTableWidgetItem("" if v is None else str(v))
                if c==0:item.setData(Qt.UserRole,row.get("instance_id"))
                self.instance_table.setItem(r,c,item)
        self.instance_table.resizeColumnsToContents()

    def sort_instances(self,column):
        self.sort_ascending = self.sort_column != column or not self.sort_ascending
        self.sort_column=column; self.load_instances()

    def refresh_all(self):
        self.load_models(); self.load_statuses(); self.load_instances()
        if self.current_instance_id is not None:self.show_instance_detail(self.current_instance_id)

    def open_selected_instance(self,row,_column):
        item=self.instance_table.item(row,0)
        if item:self.load_instance_into_form(item.data(Qt.UserRole) or item.text()); self.show_instance_detail(item.data(Qt.UserRole) or item.text())

    def open_current_detail(self):
        instance_id = self.current_instance_id or self._selected_table_id()
        if instance_id is not None:
            self.show_instance_detail(instance_id)

    def load_instance_into_form(self,instance_id):
        data=self.instance_repo.get_by_id(instance_id)
        if not data:return
        self.current_instance_id=instance_id
        idx=self.model_box.findData(data.get("motor_model_id"))
        if idx>=0:self.model_box.setCurrentIndex(idx)
        self.serial_edit.setText(str(data.get("serial_number") or ""))
        self.nickname_edit.setText(str(data.get("nickname") or ""))
        idx=self.status_box.findText(str(data.get("status") or ""))
        if idx>=0:self.status_box.setCurrentIndex(idx)

    def clear_form(self):
        self.current_instance_id=None
        if self.model_box.count():self.model_box.setCurrentIndex(0)
        self.serial_edit.clear(); self.nickname_edit.clear()
        if self.status_box.count():self.status_box.setCurrentIndex(0)
        self.detail_title.setText("New Motor Instance")

    def save_instance(self):
        if self.current_instance_id is None:
            QMessageBox.information(self,"Instance","新規Instance登録は既存UIの仕様を使用してください。今回の再設計では既存登録ロジックを変更しません。")
            return
        data={"motor_model_id":self.model_box.currentData(),"serial_number":self.serial_edit.text().strip(),
              "nickname":self.nickname_edit.text().strip(),"status":self.status_box.currentText()}
        cols={r[1] for r in self.db.execute("PRAGMA table_info(motor_instance)").fetchall()}
        data={k:v for k,v in data.items() if k in cols}
        try:
            self.instance_repo.update_instance(self.current_instance_id,data)
            self.load_instances(); self.show_instance_detail(self.current_instance_id)
        except Exception as exc: QMessageBox.critical(self,"Save Error",str(exc))

    def set_visibility(self,value):
        iid=self.current_instance_id or self._selected_table_id()
        if iid is None:return
        try:self.visibility.set(iid,value); self.load_instances(); self.show_instance_detail(iid)
        except Exception as exc:QMessageBox.critical(self,"Visibility",str(exc))

    def _selected_table_id(self):
        rows=self.instance_table.selectionModel().selectedRows()
        if not rows:return None
        return self.instance_table.item(rows[0].row(),0).data(Qt.UserRole)

    def show_instance_detail(self,instance_id):
        data=self.instance_repo.get_by_id(instance_id)
        if not data:return
        self.current_instance_id=str(instance_id)
        self.detail_title.setText(f"Instance {instance_id} — {data.get('nickname') or data.get('serial_number') or ''} — {self.visibility.get(instance_id)}")
        self.load_instance_into_form(instance_id)

        # RawLog is the authoritative local measurement record. Do not require
        # a matching DB Measurement Session just to make an existing RawLog
        # visible. A DB session, when present, is attached as context.
        sessions=self.instance_repo.get_sessions(instance_id)
        session_by_id={str(s.get("session_id")):s for s in sessions if s.get("session_id") is not None}

        self.history_table.setRowCount(0)
        logs=[x for x in self.raw_library.list_logs("MOTOR")
              if str(x.device_instance_id)==str(instance_id)]

        for log in logs:
            session=session_by_id.get(str(log.measurement_session_id))
            self._add_history_row(session,log)

        self.history_table.resizeColumnsToContents()

    def _add_history_row(self,session,log):
        r=self.history_table.rowCount(); self.history_table.insertRow(r)

        sid=str(session.get("session_id")) if session else str(log.measurement_session_id or "—")
        note=log.notes if log else "—"
        logid=log.log_id if log else "—"
        history="REGISTERED" if log and log.history_registered == "1" else "—"
        github=self.raw_library.get_github_status(log.log_id).get("status","UNREGISTERED") if log else "—"

        if session:
            date=session.get("end_datetime") or session.get("start_datetime") or session.get("created_at") or ""
            device_type=session.get("device_type") or ""
            result=session.get("result") or ""
        else:
            date=log.acquired_at or ""
            device_type=log.device_type or ""
            result=""

        integrity=self._integrity(session,log) if log else "NO RAW LOG"
        vals=[sid,date,device_type,note,logid,history,github,integrity,result]

        for c,v in enumerate(vals):
            item=QTableWidgetItem(str(v))
            if log and c==4:item.setData(Qt.UserRole,log.log_id)
            self.history_table.setItem(r,c,item)

    def _integrity(self,session,log):
        if session is None:
            return "NO SESSION"
        if str(session.get("instance_id")) != str(log.device_instance_id):
            return "Relationship Error"
        return "OK"

    def _selected_log(self):
        rows=self.history_table.selectionModel().selectedRows()
        if not rows:return None
        row=rows[0].row(); item=self.history_table.item(row,4)
        if not item or item.text()=="—":return None
        return item.data(Qt.UserRole) or item.text()

    def register_history(self):
        logid=self._selected_log()
        if not logid:
            QMessageBox.information(self,"History","History登録するRawLog行を選択してください。"); return
        try:
            self.raw_library.set_history_registered(logid,True)
            self.show_instance_detail(self.current_instance_id)
        except Exception as exc:QMessageBox.critical(self,"History",str(exc))

    def remove_history(self):
        logid=self._selected_log()
        if not logid:return
        if QMessageBox.question(self,"History","History表示対象から外しますか？\nRawLog / Session / Instance / 測定データは削除されません。",
                                QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        try:self.raw_library.set_history_registered(logid,False); self.show_instance_detail(self.current_instance_id)
        except Exception as exc:QMessageBox.critical(self,"History",str(exc))

    def edit_note(self):
        logid=self._selected_log()
        if not logid:return
        record,_,_=self.raw_library.get(logid)
        value,ok=QInputDialog.getText(self,"RawLog Note","測定への補足情報:",text=record.notes or "")
        if not ok:return
        try:self.raw_library.update_metadata(logid,notes=value); self.show_instance_detail(self.current_instance_id)
        except Exception as exc:QMessageBox.critical(self,"Note",str(exc))

    def register_github(self):
        logid=self._selected_log()
        if not logid:return
        status=self.raw_library.get_github_status(logid)
        if status.get("status")=="REGISTERED":
            QMessageBox.information(self,"GitHub",f"{logid} は既にGitHub登録済みです。"); return
        if QMessageBox.question(self,"GitHub登録","このRawLogを解析・検証用としてGitHubへ登録しますか？",
                                QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        try:
            result=GitHubRawLogExporter(self.raw_library).register(logid)
            self.show_instance_detail(self.current_instance_id)
            QMessageBox.information(self,"GitHub",f"登録完了\n{result.get('repository')}\n{result.get('commit','')}")
        except GitHubRegistrationError as exc: QMessageBox.critical(self,"GitHub",str(exc))
        except Exception as exc: QMessageBox.critical(self,"GitHub",str(exc))

    def relink_raw_log(self):
        logid=self._selected_log()
        if not logid:return
        record,_,_=self.raw_library.get(logid)
        instances=self.instance_repo.get_all_active()
        ids=[str(x.get("instance_id")) for x in instances]
        if not ids:return
        target,ok=QInputDialog.getItem(self,"RawLog Relink","Target Instance:",ids,0,False)
        if not ok or not target:return
        session_id=record.measurement_session_id
        session=self.db.execute("SELECT instance_id FROM measurement_session WHERE session_id=?",(str(session_id),)).fetchone() if session_id else None
        session_instance=session[0] if session else None
        same=[x for x in self.raw_library.list_by_session(str(session_id))] if session_id else []
        details=[f"RawLog: {logid}",f"Current Instance: {record.device_instance_id or '—'}",
                 f"Target Instance: {target}",f"Session ID: {session_id or '—'}",
                 f"Session Instance: {session_instance or '—'}",
                 f"Same-session RawLogs: {', '.join(x.log_id+':'+str(x.device_instance_id) for x in same) or '—'}"]
        if QMessageBox.question(self,"RawLog Relink — Confirm","\n".join(details)+"\n\n関連付けだけを変更しますか？",
                                QMessageBox.Yes|QMessageBox.No,QMessageBox.No)!=QMessageBox.Yes:return
        try:
            self.raw_library.update_metadata(logid,device_instance_id=str(target))
            self.show_instance_detail(self.current_instance_id)
            self.load_instances()
        except Exception as exc: QMessageBox.critical(self,"Relink",str(exc))

    def view_raw_body(self):
        logid=self._selected_log()
        if not logid:return
        try: body=self.raw_library.read_raw(logid)
        except Exception as exc: QMessageBox.critical(self,"RawLog",str(exc)); return
        dialog=QDialog(self); dialog.setWindowTitle(f"Raw Body — {logid}"); dialog.resize(1000,700)
        layout=QVBoxLayout(dialog); from PyQt5.QtWidgets import QPlainTextEdit
        view=QPlainTextEdit(); view.setReadOnly(True); view.setLineWrapMode(QPlainTextEdit.NoWrap); view.setPlainText(body)
        layout.addWidget(view); dialog.exec_()

    def closeEvent(self,event):
        self.db.close(); event.accept()


if __name__=="__main__":
    app=QApplication(sys.argv); w=MotorManagerUI(); w.show(); sys.exit(app.exec_())
