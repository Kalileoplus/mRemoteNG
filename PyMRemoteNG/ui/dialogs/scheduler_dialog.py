"""
Scheduler Dialog: crea e gestisce task programmati (comandi SSH su più host).
"""
from __future__ import annotations
from datetime import datetime
from typing import List

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QTextEdit, QDateTimeEdit, QMessageBox,
    QDialogButtonBox, QFormLayout, QSplitter, QWidget
)
from PyQt6.QtCore import QDateTime
from themes.dark_theme import ACCENT_COLOR, TEXT_COLOR, SUB_COLOR, BG_COLOR
from core.scheduler import TaskScheduler, ScheduledTask


_SCHED_COLORS = {True: "#4EC94E", False: "#888888"}


# ─────────────────────────────────────────────────────────────
# Dialogo add/edit task
# ─────────────────────────────────────────────────────────────
class TaskEditDialog(QDialog):
    def __init__(self, task: ScheduledTask = None,
                 available_hosts: List[str] = None, parent=None):
        super().__init__(parent)
        self._task   = task
        self._hosts  = available_hosts or []
        self.setWindowTitle("Nuovo task" if task is None else "Modifica task")
        self.setMinimumSize(520, 460)
        self._setup_ui()
        self._apply_style()
        if task:
            self._populate(task)

    def _apply_style(self):
        self.setStyleSheet(f"""
            QDialog   {{ background:{BG_COLOR}; color:{TEXT_COLOR}; }}
            QLabel    {{ background:transparent; color:{TEXT_COLOR}; }}
            QLineEdit, QComboBox, QDateTimeEdit, QTextEdit {{
                background:#1E1E1E; color:{TEXT_COLOR};
                border:1px solid #333; border-radius:3px; padding:3px 8px;
            }}
            QLineEdit:focus, QTextEdit:focus {{ border-color:{ACCENT_COLOR}; }}
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        form.setSpacing(8)

        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("es. Backup notturno")
        form.addRow("Nome task:", self._name_edit)

        self._stype_combo = QComboBox()
        self._stype_combo.addItems(["Una volta (once)", "Ogni giorno (daily)", "Ogni settimana (weekly)"])
        form.addRow("Frequenza:", self._stype_combo)

        self._dt_edit = QDateTimeEdit()
        self._dt_edit.setDateTime(QDateTime.currentDateTime())
        self._dt_edit.setDisplayFormat("dd/MM/yyyy HH:mm")
        self._dt_edit.setCalendarPopup(True)
        form.addRow("Data/Ora esecuzione:", self._dt_edit)

        self._proto_combo = QComboBox()
        self._proto_combo.addItems(["SSH2", "Telnet"])
        form.addRow("Protocollo:", self._proto_combo)

        layout.addLayout(form)

        # Host
        host_lbl = QLabel("Host target (uno per riga):")
        host_lbl.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px;")
        layout.addWidget(host_lbl)
        self._hosts_edit = QTextEdit()
        self._hosts_edit.setFixedHeight(80)
        self._hosts_edit.setPlaceholderText("192.168.1.10\n192.168.1.20\nserver01")
        if self._hosts:
            self._hosts_edit.setPlainText("\n".join(self._hosts))
        layout.addWidget(self._hosts_edit)

        # Comando
        cmd_lbl = QLabel("Comando da eseguire:")
        cmd_lbl.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px;")
        layout.addWidget(cmd_lbl)
        self._cmd_edit = QTextEdit()
        self._cmd_edit.setFixedHeight(80)
        self._cmd_edit.setPlaceholderText("es. df -h && uptime")
        layout.addWidget(self._cmd_edit)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.setStyleSheet(f"""
            QPushButton {{ background:{ACCENT_COLOR}; color:white; border:none;
                          border-radius:3px; padding:5px 18px; }}
            QPushButton:hover {{ background:#0088DD; }}
        """)
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _populate(self, t: ScheduledTask):
        self._name_edit.setText(t.name)
        type_map = {"once": 0, "daily": 1, "weekly": 2}
        self._stype_combo.setCurrentIndex(type_map.get(t.schedule_type, 0))
        if t.run_at:
            try:
                dt = QDateTime.fromString(t.run_at, Qt.DateFormat.ISODate)
                if dt.isValid():
                    self._dt_edit.setDateTime(dt)
            except Exception:
                pass
        idx = self._proto_combo.findText(t.protocol)
        if idx >= 0:
            self._proto_combo.setCurrentIndex(idx)
        self._hosts_edit.setPlainText("\n".join(t.target_hosts))
        self._cmd_edit.setPlainText(t.command)

    def _validate(self):
        if not self._name_edit.text().strip():
            QMessageBox.warning(self, "Errore", "Nome task obbligatorio.")
            return
        if not self._cmd_edit.toPlainText().strip():
            QMessageBox.warning(self, "Errore", "Comando obbligatorio.")
            return
        hosts = [h.strip() for h in self._hosts_edit.toPlainText().splitlines() if h.strip()]
        if not hosts:
            QMessageBox.warning(self, "Errore", "Inserisci almeno un host target.")
            return
        self.accept()

    def get_data(self) -> dict:
        stype_map = {0: "once", 1: "daily", 2: "weekly"}
        hosts = [h.strip() for h in self._hosts_edit.toPlainText().splitlines() if h.strip()]
        dt_iso = self._dt_edit.dateTime().toString(Qt.DateFormat.ISODate)
        return {
            "name":          self._name_edit.text().strip(),
            "schedule_type": stype_map[self._stype_combo.currentIndex()],
            "run_at":        dt_iso,
            "protocol":      self._proto_combo.currentText(),
            "target_hosts":  hosts,
            "command":       self._cmd_edit.toPlainText().strip(),
        }


# ─────────────────────────────────────────────────────────────
# Dialogo principale scheduler
# ─────────────────────────────────────────────────────────────
class SchedulerDialog(QDialog):
    def __init__(self, available_hosts: List[str] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Script Scheduler")
        self.setMinimumSize(780, 520)
        self._sched = TaskScheduler.get_instance()
        self._available_hosts = available_hosts or []
        self._setup_ui()
        self._apply_style()
        self._refresh()

    def _apply_style(self):
        self.setStyleSheet(f"""
            QDialog {{ background:{BG_COLOR}; color:{TEXT_COLOR}; }}
            QLabel  {{ background:transparent; color:{TEXT_COLOR}; }}
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("Script Scheduler")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{ACCENT_COLOR};")
        layout.addWidget(title)

        subtitle = QLabel(
            "Pianifica comandi SSH da eseguire automaticamente su gruppi di host."
        )
        subtitle.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px;")
        layout.addWidget(subtitle)

        # Toolbar
        toolbar = QHBoxLayout()
        add_btn = QPushButton("+ Nuovo task")
        add_btn.setStyleSheet(f"""
            QPushButton {{ background:{ACCENT_COLOR}; color:white; border:none;
                          border-radius:3px; padding:5px 14px; font-weight:bold; }}
            QPushButton:hover {{ background:#0088DD; }}
        """)
        add_btn.clicked.connect(self._add_task)
        toolbar.addWidget(add_btn)

        self._edit_btn   = QPushButton("Modifica")
        self._del_btn    = QPushButton("Elimina")
        self._toggle_btn = QPushButton("Abilita/Disabilita")
        for btn in [self._edit_btn, self._del_btn, self._toggle_btn]:
            btn.setEnabled(False)
            btn.setStyleSheet(
                f"QPushButton {{ background:#2A2A2A; color:{TEXT_COLOR}; border:1px solid #444;"
                f" border-radius:3px; padding:5px 12px; }}"
                f"QPushButton:hover {{ background:#3A3A3A; }}"
                f"QPushButton:disabled {{ color:#555; border-color:#333; }}"
            )
            toolbar.addWidget(btn)

        self._edit_btn.clicked.connect(self._edit_task)
        self._del_btn.clicked.connect(self._delete_task)
        self._toggle_btn.clicked.connect(self._toggle_task)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Tabella
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["Nome", "Frequenza", "Prossima esecuzione", "Host", "Ultimo run", "Stato"]
        )
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(1, 100)
        self._table.setColumnWidth(2, 145)
        self._table.setColumnWidth(3, 80)
        self._table.setColumnWidth(4, 145)
        self._table.setColumnWidth(5, 80)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.itemSelectionChanged.connect(self._on_selection)
        self._table.setStyleSheet(f"""
            QTableWidget {{ background:{BG_COLOR}; color:{TEXT_COLOR};
                           border:1px solid #2A2A2A; alternate-background-color:#111; }}
            QHeaderView::section {{ background:#1A1A1A; color:{SUB_COLOR};
                                    border:none; padding:4px 8px; font-size:11px; }}
            QTableWidget::item:selected {{ background:#1A3A5A; color:white; }}
        """)
        layout.addWidget(self._table)

        footer = QHBoxLayout()
        footer.addStretch()
        close_btn = QPushButton("Chiudi")
        close_btn.setStyleSheet(
            f"QPushButton {{ background:#2A2A2A; color:{TEXT_COLOR}; border:1px solid #444;"
            f" border-radius:4px; padding:6px 16px; }}"
            f"QPushButton:hover {{ background:#3A3A3A; }}"
        )
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        layout.addLayout(footer)

    def _refresh(self):
        self._table.setRowCount(0)
        for task in self._sched.all():
            row = self._table.rowCount()
            self._table.insertRow(row)

            name_item = QTableWidgetItem(task.name)
            name_item.setData(Qt.ItemDataRole.UserRole, task.id)
            self._table.setItem(row, 0, name_item)

            stype_labels = {"once": "Una volta", "daily": "Giornaliero", "weekly": "Settimanale"}
            self._table.setItem(row, 1, QTableWidgetItem(stype_labels.get(task.schedule_type, task.schedule_type)))
            self._table.setItem(row, 2, QTableWidgetItem(task.run_at[:16].replace("T", " ") if task.run_at else "—"))
            self._table.setItem(row, 3, QTableWidgetItem(str(len(task.target_hosts))))
            self._table.setItem(row, 4, QTableWidgetItem(task.last_run[:16].replace("T", " ") if task.last_run else "Mai"))

            status_item = QTableWidgetItem("Attivo" if task.enabled else "Disabilitato")
            status_item.setForeground(QColor("#4EC94E" if task.enabled else "#888"))
            self._table.setItem(row, 5, status_item)

    def _on_selection(self):
        has = bool(self._table.selectedItems())
        for btn in [self._edit_btn, self._del_btn, self._toggle_btn]:
            btn.setEnabled(has)

    def _selected_task_id(self):
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _add_task(self):
        dlg = TaskEditDialog(available_hosts=self._available_hosts, parent=self)
        if dlg.exec():
            d = dlg.get_data()
            self._sched.add(
                d["name"], d["command"], d["target_hosts"],
                d["protocol"], d["schedule_type"], d["run_at"]
            )
            self._refresh()

    def _edit_task(self):
        tid = self._selected_task_id()
        if not tid:
            return
        task = next((t for t in self._sched.all() if t.id == tid), None)
        if not task:
            return
        dlg = TaskEditDialog(task=task, available_hosts=self._available_hosts, parent=self)
        if dlg.exec():
            d = dlg.get_data()
            self._sched.update(
                tid, name=d["name"], command=d["command"],
                target_hosts=d["target_hosts"], protocol=d["protocol"],
                schedule_type=d["schedule_type"], run_at=d["run_at"]
            )
            self._refresh()

    def _delete_task(self):
        tid = self._selected_task_id()
        if not tid:
            return
        r = QMessageBox.question(self, "Elimina", "Eliminare questo task?",
                                 QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            self._sched.delete(tid)
            self._refresh()

    def _toggle_task(self):
        tid = self._selected_task_id()
        if not tid:
            return
        task = next((t for t in self._sched.all() if t.id == tid), None)
        if task:
            self._sched.update(tid, enabled=not task.enabled)
            self._refresh()
