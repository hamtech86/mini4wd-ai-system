"""Motor Instance Manager used by the break-in operator UI."""
import sqlite3
import sys
from pathlib import Path
from PyQt5.QtWidgets import QApplication,QComboBox,QHBoxLayout,QLabel,QLineEdit,QMessageBox,QPushButton,QTableWidget,QTableWidgetItem,QVBoxLayout,QWidget,QHeaderView

ROOT=Path(__file__).resolve().parents[3]
DB_PATH=ROOT/"database"/"mini4wd.db"

class MotorManagerUI(QWidget):
    def __init__(self):
        super().__init__(); self.setWindowTitle("Motor Instance Manager"); self.resize(820,600); self.setMinimumSize(760,520); self.editing_instance_id=None; self.build_ui(); self.load_all()
    def db(self): return sqlite3.connect(DB_PATH)
    def build_ui(self):
        layout=QVBoxLayout(self)
        r=QHBoxLayout(); r.addWidget(QLabel("Motor Model")); self.model_box=QComboBox(); r.addWidget(self.model_box,1); layout.addLayout(r)
        r=QHBoxLayout(); r.addWidget(QLabel("Serial Number")); self.serial_edit=QLineEdit(); r.addWidget(self.serial_edit,1); layout.addLayout(r)
        r=QHBoxLayout(); r.addWidget(QLabel("Nickname")); self.name_edit=QLineEdit(); r.addWidget(self.name_edit,1); layout.addLayout(r)
        b=QHBoxLayout(); self.register_button=QPushButton("Register"); self.update_button=QPushButton("Update Selected"); self.clear_button=QPushButton("Clear / New"); self.register_button.clicked.connect(self.register_motor); self.update_button.clicked.connect(self.update_selected); self.clear_button.clicked.connect(self.clear_editor); self.update_button.setEnabled(False); b.addWidget(self.register_button); b.addWidget(self.update_button); b.addWidget(self.clear_button); layout.addLayout(b)
        self.table=QTableWidget(0,5); self.table.setHorizontalHeaderLabels(["ID","Model ID","Serial","Nickname","Status"]); self.table.setSelectionBehavior(QTableWidget.SelectRows); self.table.setSelectionMode(QTableWidget.SingleSelection); self.table.itemSelectionChanged.connect(self.on_selection_changed); self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch); layout.addWidget(self.table,1)
    def load_all(self): self.load_models(); self.load_instances()
    def load_models(self):
        self.model_box.clear()
        with self.db() as c:
            rows=c.execute("SELECT motor_model_id,name FROM motor_model WHERE COALESCE(is_deleted,0)=0 ORDER BY name").fetchall()
        for mid,name in rows:self.model_box.addItem(str(name),mid)
    def load_instances(self):
        with self.db() as c:
            rows=c.execute("SELECT instance_id,motor_model_id,serial_number,nickname,status FROM motor_instance WHERE COALESCE(is_deleted,0)=0 ORDER BY instance_id DESC").fetchall()
        self.table.setRowCount(len(rows))
        for r,row in enumerate(rows):
            for col,value in enumerate(row): self.table.setItem(r,col,QTableWidgetItem(str(value or "")))
    def register_motor(self):
        mid=self.model_box.currentData()
        if mid is None:return QMessageBox.warning(self,"Motor Model","Motor Modelを選択してください。")
        with self.db() as c:
            c.execute("INSERT INTO motor_instance (motor_model_id,serial_number,nickname,status,is_deleted) VALUES (?,?,?,?,0)",(mid,self.serial_edit.text().strip(),self.name_edit.text().strip(),"NEW")); c.commit()
        self.load_instances(); self.clear_editor(); QMessageBox.information(self,"Complete","Motor Instanceを登録しました。")
    def on_selection_changed(self):
        row=self.table.currentRow()
        if row<0:return
        try:self.editing_instance_id=int(self.table.item(row,0).text())
        except Exception:return
        mid=int(self.table.item(row,1).text()); self.model_box.setCurrentIndex(max(0,self.model_box.findData(mid))); self.serial_edit.setText(self.table.item(row,2).text()); self.name_edit.setText(self.table.item(row,3).text()); self.update_button.setEnabled(True)
    def update_selected(self):
        if self.editing_instance_id is None:return
        mid=self.model_box.currentData()
        with self.db() as c:
            c.execute("UPDATE motor_instance SET motor_model_id=?,serial_number=?,nickname=?,updated_at=CURRENT_TIMESTAMP WHERE instance_id=?",(mid,self.serial_edit.text().strip(),self.name_edit.text().strip(),self.editing_instance_id)); c.commit()
        self.load_instances(); self.clear_editor(); QMessageBox.information(self,"Updated",f"Motor Instance ID={self.editing_instance_id} を更新しました。")
    def clear_editor(self):
        self.editing_instance_id=None; self.serial_edit.clear(); self.name_edit.clear(); self.table.clearSelection(); self.update_button.setEnabled(False)
        if self.model_box.count():self.model_box.setCurrentIndex(0)

if __name__=="__main__":
    app=QApplication(sys.argv); w=MotorManagerUI(); w.show(); sys.exit(app.exec_())
