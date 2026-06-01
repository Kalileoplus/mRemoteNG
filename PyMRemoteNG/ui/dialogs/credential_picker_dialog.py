"""
Dialogo per scegliere le credenziali prima di una connessione RDP.
Mostra le credenziali salvate + opzione di usare quelle della connessione.
"""
from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QLineEdit, QCheckBox,
    QDialogButtonBox, QGroupBox, QFormLayout, QWidget, QFrame
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont, QColor

from themes.dark_theme import ACCENT_COLOR, TEXT_COLOR, SUB_COLOR, CARD_COLOR

if TYPE_CHECKING:
    from core.models import ConnectionInfo
    from core.credentials import SavedCredential


_INPUT_STYLE = (
    f"background:#0C0C0C; color:{TEXT_COLOR}; border:1px solid #333; "
    f"border-radius:3px; padding:4px 8px; font-size:12px;"
)
_BTN_ACCENT = (
    f"background:{ACCENT_COLOR}; color:white; border:none; "
    f"border-radius:3px; padding:5px 18px; font-size:12px;"
)
_BTN_FLAT = (
    f"background:#2A2A2A; color:{TEXT_COLOR}; border:1px solid #333; "
    f"border-radius:3px; padding:5px 18px; font-size:12px;"
)


class CredentialPickerDialog(QDialog):
    """
    Mostra le credenziali salvate e permette di:
    - Selezionarne una (username + password già salvata, basta confermare)
    - Usare quelle della connessione
    - Inserire nuove credenziali al volo (e salvarle opzionalmente)
    """

    def __init__(self, conn: 'ConnectionInfo', parent=None):
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle(f"Credenziali RDP — {conn.hostname}")
        self.setMinimumSize(440, 480)
        self.setStyleSheet(f"background:#141414; color:{TEXT_COLOR};")

        from core.credentials import CredentialManager
        self._mgr   = CredentialManager.get_instance()
        self._creds = self._mgr.all()

        # Risultato finale
        self.result_username: str = conn.username
        self.result_password: str = ""
        self.result_domain:   str = conn.domain if hasattr(conn, "domain") else ""

        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 14, 16, 14)

        # Titolo
        title = QLabel(f"Connessione RDP a  <b>{self.conn.hostname}:{self.conn.port}</b>")
        title.setStyleSheet(f"color:{TEXT_COLOR}; font-size:13px; background:transparent;")
        layout.addWidget(title)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("border:1px solid #2A2A2A;")
        layout.addWidget(sep)

        # Sezione credenziali salvate
        saved_label = QLabel("Credenziali salvate:")
        saved_label.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px; background:transparent;")
        layout.addWidget(saved_label)

        self.cred_list = QListWidget()
        self.cred_list.setFixedHeight(140)
        self.cred_list.setStyleSheet(f"""
            QListWidget {{
                background:#0C0C0C; color:{TEXT_COLOR};
                border:1px solid #2A2A2A; border-radius:3px; font-size:12px;
                outline:none;
            }}
            QListWidget::item {{ padding:6px 10px; }}
            QListWidget::item:selected {{ background:{ACCENT_COLOR}; color:white; }}
            QListWidget::item:hover:!selected {{ background:#1E1E1E; }}
        """)
        self.cred_list.itemSelectionChanged.connect(self._on_cred_selected)
        layout.addWidget(self.cred_list)

        # Pulsanti gestione credenziali
        mgmt_row = QHBoxLayout()
        self._btn_add_cred = QPushButton("＋ Salva nuova")
        self._btn_del_cred = QPushButton("✕ Elimina")
        for btn, cb in [(self._btn_add_cred, self._on_save_new_cred),
                        (self._btn_del_cred, self._on_delete_cred)]:
            btn.setStyleSheet(_BTN_FLAT)
            btn.setFixedHeight(26)
            btn.clicked.connect(cb)
            mgmt_row.addWidget(btn)
        mgmt_row.addStretch()
        layout.addLayout(mgmt_row)

        sep2 = QFrame()
        sep2.setFrameShape(QFrame.Shape.HLine)
        sep2.setStyleSheet("border:1px solid #2A2A2A;")
        layout.addWidget(sep2)

        # Credenziali manuali
        manual_label = QLabel("Oppure inserisci manualmente:")
        manual_label.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px; background:transparent;")
        layout.addWidget(manual_label)

        form = QFormLayout()
        form.setSpacing(6)

        def lbl(txt):
            l = QLabel(txt)
            l.setStyleSheet(f"color:{SUB_COLOR}; background:transparent; font-size:11px;")
            return l

        self.user_edit = QLineEdit(self.conn.username)
        self.user_edit.setStyleSheet(_INPUT_STYLE)
        self.user_edit.setFixedHeight(28)

        self.pass_edit = QLineEdit()
        self.pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.pass_edit.setPlaceholderText("password")
        self.pass_edit.setStyleSheet(_INPUT_STYLE)
        self.pass_edit.setFixedHeight(28)

        self.domain_edit = QLineEdit(getattr(self.conn, "domain", ""))
        self.domain_edit.setPlaceholderText("opzionale")
        self.domain_edit.setStyleSheet(_INPUT_STYLE)
        self.domain_edit.setFixedHeight(28)

        form.addRow(lbl("Utente:"),   self.user_edit)
        form.addRow(lbl("Password:"), self.pass_edit)
        form.addRow(lbl("Dominio:"),  self.domain_edit)
        layout.addLayout(form)

        self.save_check = QCheckBox("Salva queste credenziali per usi futuri")
        self.save_check.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px; background:transparent;")
        layout.addWidget(self.save_check)

        layout.addStretch()

        # Bottoni principali
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("Annulla")
        btn_cancel.setStyleSheet(_BTN_FLAT)
        btn_cancel.setFixedHeight(32)
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        btn_conn = QPushButton("▶  Connetti")
        btn_conn.setStyleSheet(_BTN_ACCENT)
        btn_conn.setFixedHeight(32)
        btn_conn.setDefault(True)
        btn_conn.clicked.connect(self._on_connect)
        btn_row.addWidget(btn_conn)
        layout.addLayout(btn_row)

    def _refresh_list(self):
        self.cred_list.clear()
        # Prima voce: credenziali della connessione
        item0 = QListWidgetItem(f"  🔑  Usa credenziali connessione  [{self.conn.username or '—'}]")
        item0.setData(Qt.ItemDataRole.UserRole, None)
        item0.setForeground(QColor(SUB_COLOR))
        self.cred_list.addItem(item0)

        for cred in self._creds:
            label = f"  👤  {cred.name}  |  {cred.username}"
            if cred.domain:
                label += f"  |  {cred.domain}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, cred)
            self.cred_list.addItem(item)

    def _on_cred_selected(self):
        items = self.cred_list.selectedItems()
        if not items:
            return
        cred = items[0].data(Qt.ItemDataRole.UserRole)
        if cred is None:
            # usa credenziali connessione
            self.user_edit.setText(self.conn.username)
            self.pass_edit.setText("")
            self.domain_edit.setText(getattr(self.conn, "domain", ""))
        else:
            self.user_edit.setText(cred.username)
            self.pass_edit.setText(cred.get_password())
            self.domain_edit.setText(cred.domain)

    def _on_connect(self):
        if self.save_check.isChecked():
            self._mgr.add(
                name=self.user_edit.text().strip(),
                username=self.user_edit.text().strip(),
                password=self.pass_edit.text(),
                domain=self.domain_edit.text().strip(),
            )
        self.result_username = self.user_edit.text().strip()
        self.result_password = self.pass_edit.text()
        self.result_domain   = self.domain_edit.text().strip()
        self.accept()

    def _on_save_new_cred(self):
        """Salva le credenziali inserite nel form come nuova voce."""
        u = self.user_edit.text().strip()
        p = self.pass_edit.text()
        d = self.domain_edit.text().strip()
        if not u:
            return
        self._mgr.add(name=u, username=u, password=p, domain=d)
        self._creds = self._mgr.all()
        self._refresh_list()

    def _on_delete_cred(self):
        items = self.cred_list.selectedItems()
        if not items:
            return
        cred = items[0].data(Qt.ItemDataRole.UserRole)
        if cred is None:
            return
        self._mgr.delete(cred.id)
        self._creds = self._mgr.all()
        self._refresh_list()
