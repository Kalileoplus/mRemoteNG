"""
MultiExec: invia lo stesso comando a tutte le sessioni SSH aperte.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QCheckBox,
    QDialogButtonBox, QFrame, QTextEdit
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from themes.dark_theme import ACCENT_COLOR, CARD_COLOR, TEXT_COLOR, SUB_COLOR, BG_COLOR


class MultiExecDialog(QDialog):
    """
    Dialogo MultiExec stile MobaXterm:
    - Lista sessioni SSH aperte con checkbox
    - Campo input comando
    - Invio a tutte le sessioni selezionate
    """
    def __init__(self, open_tabs: dict, parent=None):
        super().__init__(parent)
        self.open_tabs = open_tabs
        self.setWindowTitle("MultiExec — Broadcast Command")
        self.setMinimumSize(500, 400)
        self.setStyleSheet(f"QDialog {{ background: {CARD_COLOR}; color: {TEXT_COLOR}; }}")
        self._setup_ui()
        self._populate_sessions()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 12)

        # Header
        hdr = QLabel("⚡  MultiExec — Esegui comando su più sessioni")
        hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {TEXT_COLOR}; background: transparent;")
        layout.addWidget(hdr)

        sub = QLabel("Seleziona le sessioni su cui eseguire il comando:")
        sub.setStyleSheet(f"color: {SUB_COLOR}; background: transparent;")
        layout.addWidget(sub)

        # Lista sessioni con checkbox
        self.session_list = QListWidget()
        self.session_list.setStyleSheet(f"""
            QListWidget {{
                background: #141414; color: {TEXT_COLOR};
                border: 1px solid #2A2A2A; border-radius: 3px;
            }}
            QListWidget::item {{ padding: 5px 8px; }}
            QListWidget::item:hover {{ background: #1E1E1E; }}
            QListWidget::item:selected {{ background: {ACCENT_COLOR}; }}
        """)
        layout.addWidget(self.session_list)

        # Selezione rapida
        sel_row = QHBoxLayout()
        for label, fn in [("Seleziona tutto", self._select_all),
                          ("Deseleziona tutto", self._deselect_all)]:
            btn = QPushButton(label)
            btn.setFixedHeight(26)
            btn.setStyleSheet(f"""
                QPushButton {{ background: #2A2A2A; color: {TEXT_COLOR};
                    border: 1px solid #333; border-radius: 3px; padding: 0 12px; font-size: 11px; }}
                QPushButton:hover {{ background: #3A3A3A; }}
            """)
            btn.clicked.connect(fn)
            sel_row.addWidget(btn)
        sel_row.addStretch()
        layout.addLayout(sel_row)

        # Separatore
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color: #2A2A2A;")
        layout.addWidget(sep)

        # Campo comando
        cmd_label = QLabel("Comando da eseguire:")
        cmd_label.setStyleSheet(f"color: {SUB_COLOR}; background: transparent;")
        layout.addWidget(cmd_label)

        self.cmd_input = QLineEdit()
        self.cmd_input.setPlaceholderText("es: ls -la  oppure  systemctl status nginx")
        self.cmd_input.setFont(QFont("Consolas", 11))
        self.cmd_input.setStyleSheet(f"""
            QLineEdit {{ background: #1E1E1E; color: {TEXT_COLOR};
                border: 1px solid #333; border-radius: 3px; padding: 6px 10px; }}
            QLineEdit:focus {{ border-color: {ACCENT_COLOR}; }}
        """)
        self.cmd_input.returnPressed.connect(self._execute)
        layout.addWidget(self.cmd_input)

        # Output log
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(80)
        self.log.setFont(QFont("Consolas", 10))
        self.log.setStyleSheet(f"""
            QTextEdit {{ background: #0C0C0C; color: #4EC94E;
                border: 1px solid #2A2A2A; border-radius: 3px; padding: 4px; }}
        """)
        layout.addWidget(self.log)

        # Bottoni
        btn_row = QHBoxLayout()
        exec_btn = QPushButton("⚡  Esegui su selezionate")
        exec_btn.setFixedHeight(34)
        exec_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        exec_btn.setStyleSheet(f"""
            QPushButton {{ background: {ACCENT_COLOR}; color: white;
                border: none; border-radius: 3px; padding: 0 20px; }}
            QPushButton:hover {{ background: #0088DD; }}
        """)
        exec_btn.clicked.connect(self._execute)
        btn_row.addWidget(exec_btn)

        close_btn = QPushButton("Chiudi")
        close_btn.setFixedHeight(34)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: #2A2A2A; color: {TEXT_COLOR};
                border: 1px solid #333; border-radius: 3px; padding: 0 16px; }}
            QPushButton:hover {{ background: #3A3A3A; }}
        """)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _populate_sessions(self):
        from ui.main_window import ConnectionTab
        self.session_list.clear()
        for conn_id, tab in self.open_tabs.items():
            if not isinstance(tab, ConnectionTab):
                continue
            if tab._protocol and tab._protocol.is_connected:
                item = QListWidgetItem(f"🟢  {tab.conn.name}  [{tab.conn.protocol.value}]  —  {tab.conn.hostname}")
                item.setData(Qt.ItemDataRole.UserRole, tab)
                item.setCheckState(Qt.CheckState.Checked)
                self.session_list.addItem(item)

        if self.session_list.count() == 0:
            item = QListWidgetItem("Nessuna sessione SSH attiva.")
            item.setForeground(QColor(SUB_COLOR))
            self.session_list.addItem(item)

    def _select_all(self):
        for i in range(self.session_list.count()):
            item = self.session_list.item(i)
            if item.data(Qt.ItemDataRole.UserRole):
                item.setCheckState(Qt.CheckState.Checked)

    def _deselect_all(self):
        for i in range(self.session_list.count()):
            self.session_list.item(i).setCheckState(Qt.CheckState.Unchecked)

    def _execute(self):
        from core.user_manager import UserManager
        user = UserManager.get_instance().current_user()
        if not user or not user.can("run_scripts"):
            self.log.append("❌ Permesso negato: ruolo insufficiente per eseguire comandi.")
            return

        cmd = self.cmd_input.text().strip()
        if not cmd:
            return
        if len(cmd) > 2048:
            self.log.append("❌ Comando troppo lungo (max 2048 caratteri).")
            return
        count = 0
        for i in range(self.session_list.count()):
            item = self.session_list.item(i)
            if item.checkState() != Qt.CheckState.Checked:
                continue
            tab = item.data(Qt.ItemDataRole.UserRole)
            if tab:
                tab.send_keys(cmd + "\r")
                count += 1
        self.log.append(f"✓ Inviato a {count} sessioni.")
        self.cmd_input.clear()
        self.cmd_input.setFocus()
