"""Main-window Motor Instance selector.

Only locally VISIBLE instances are offered. Visibility is independent of the
database is_deleted flag.
"""
from __future__ import annotations
import sqlite3
from pathlib import Path
from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QComboBox,QFormLayout,QGroupBox,QHBoxLayout,QLabel,QPushButton,QDialog,QVBoxLayout,QTableWidget,QTableWidgetItem,QMessageBox

from ui.instance_visibility import InstanceVisibilityStore


class MotorInstanceUI:
    def __init__(self, window, context=None):
        self.window=window; self.context=context
        self.controller=getattr(window,"breakin_controller",None)
        self.instance_selector=QComboBox(); self.instance_label=QLabel("--")
        self.brush_peak_value=QLabel("--"); self.brush_peak_state=QLabel("--")
        self._manager_window=None; self._history_window=None
        self.visibility=InstanceVisibilityStore()
        root_layout=window.centralWidget().layout()
        box=QGroupBox("MOTOR INSTANCE"); row=QHBoxLayout(box); form=QFormLayout()
        form.addRow("Instance",self.instance_selector); form.addRow("Selected ID",self.instance_label); row.addLayout(form,1)
        b=QPushButton("MANAGER"); b.clicked.connect(self.open_manager); row.addWidget(b)
        h=QPushButton("HISTORY"); h.clicked.connect(self.open_history); row.addWidget(h)
        root_layout.insertWidget(2,box)
        peak=QGroupBox("BENCHMARK / BRUSH PEAK"); pf=QFormLayout(peak)
        pf.addRow("Peak Current",self.brush_peak_value); pf.addRow("State",self.brush_peak_state)
        root_layout.insertWidget(max(0,root_layout.count()-1),peak)
        self.instance_selector.currentIndexChanged.connect(self._instance_changed)
        self.timer=QTimer(window); self.timer.setInterval(250); self.timer.timeout.connect(self.update); self.timer.start()
        self.load_instances()

    def _database_path(self):
        return Path(__file__).resolve().parents[1] / "database" / "mini4wd.db"

    def load_instances(self):
        self.instance_selector.blockSignals(True); self.instance_selector.clear()
        path=self._database_path()
        if not path.exists():
            self.instance_selector.addItem("NO DATABASE",None); self.instance_selector.blockSignals(False); return
        try:
            db=sqlite3.connect(f"file:{path}?mode=ro",uri=True)
            rows=db.execute("""SELECT mi.instance_id,mi.motor_model_id,mi.serial_number,mi.nickname,
                                      mm.name,mm.series,mi.status
                               FROM motor_instance mi
                               LEFT JOIN motor_model mm ON mm.motor_model_id=mi.motor_model_id
                               WHERE COALESCE(mi.is_deleted,0)=0
                               ORDER BY mi.instance_id DESC""").fetchall()
            db.close()
        except sqlite3.Error as exc:
            self.instance_selector.addItem(f"DATABASE ERROR: {exc}",None); self.instance_selector.blockSignals(False); return
        rows=[r for r in rows if self.visibility.get(r[0])=="VISIBLE"]
        if not rows:self.instance_selector.addItem("NO VISIBLE MOTOR INSTANCE",None)
        for iid,mid,serial,nickname,name,series,status in rows:
            model=f"{name} ({series})" if name and series else (name or series or f"MODEL {mid}")
            label=nickname or serial or f"MODEL {mid}"
            self.instance_selector.addItem(f"{iid} / {label} / {model}",iid)
        self.instance_selector.blockSignals(False)
        self._instance_changed(self.instance_selector.currentIndex())

    def _instance_changed(self,index):
        iid=self.instance_selector.itemData(index); self.instance_label.setText(str(iid) if iid is not None else "--")
        if self.controller is not None:self.controller.selected_instance_id=iid

    def selected_instance_id(self): return self.instance_selector.currentData()

    def open_manager(self):
        from motor_system.python.ui.motor_manager_ui import MotorManagerUI
        iid=self.selected_instance_id(); self._manager_window=MotorManagerUI()
        if iid is not None:
            self._manager_window.load_instance_into_form(iid); self._manager_window.show_instance_detail(iid)
        self._manager_window.setAttribute(55,True); self._manager_window.show(); self._manager_window.raise_(); self._manager_window.activateWindow()
        self._manager_window.destroyed.connect(self.load_instances)

    def open_history(self):
        iid=self.selected_instance_id()
        if iid is None: QMessageBox.information(self.window,"History","Motor Instanceを選択してください。"); return
        db=sqlite3.connect(f"file:{self._database_path()}?mode=ro",uri=True)
        rows=db.execute("""SELECT session_id,device_type,device_model,start_datetime,end_datetime,result
                           FROM measurement_session WHERE instance_id=? ORDER BY session_id DESC""",(iid,)).fetchall()
        db.close()
        dialog=QDialog(self.window); dialog.setWindowTitle(f"Saved Sessions — Instance {iid}"); dialog.resize(850,420)
        layout=QVBoxLayout(dialog); table=QTableWidget(len(rows),6)
        table.setHorizontalHeaderLabels(["Session","Device","Model","Start","End","Result"]); table.setEditTriggers(QTableWidget.NoEditTriggers)
        for r,row in enumerate(rows):
            for c,v in enumerate(row):table.setItem(r,c,QTableWidgetItem("" if v is None else str(v)))
        table.resizeColumnsToContents(); layout.addWidget(table)
        self._history_window=dialog; dialog.show(); dialog.raise_(); dialog.activateWindow()

    def update(self):
        c=self.controller
        if c is None:return
        values=[]
        for m in list(getattr(c,"measurements",[]) or []):
            v=m.get("brush_peak_current") if isinstance(m,dict) else getattr(m,"brush_peak_current",None)
            try:
                if v is not None:values.append(float(v))
            except (TypeError,ValueError):pass
        peak=max(values,default=float(getattr(c,"last_brush_peak_current",0.0) or 0.0))
        self.brush_peak_value.setText(f"{peak:.3f} A" if peak>0 else "--")
        reached=bool(getattr(c,"brush_peak_reached",False)); target=float(getattr(c,"brush_peak_target_current",0.0) or 0.0)
        self.brush_peak_state.setText(f"APPROACH TARGET {target:.3f} A"+(" / REACHED" if reached else "") if target>0 else ("MEASURED / BENCHMARK" if peak>0 else "NO PEAK DATA"))


def install_motor_instance_ui(window, context=None):
    ui=MotorInstanceUI(window,context); window.motor_instance_ui=ui; return ui
