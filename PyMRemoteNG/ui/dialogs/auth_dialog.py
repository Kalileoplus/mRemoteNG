"""
Dialogo di autenticazione unificato per SSH, Telnet e altri protocolli.
Mostra logo chiave, host/porta, credenziali salvate e form manuale.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QColor, QFont, QPainter, QPainterPath, QPixmap, QIcon
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QCheckBox,
    QFrame, QFormLayout, QWidget
)
from themes.dark_theme import ACCENT_COLOR, TEXT_COLOR, SUB_COLOR, BG_COLOR, CARD_COLOR

if TYPE_CHECKING:
    from core.models import ConnectionInfo

_INPUT = (
    f"background:#0C0C0C; color:{TEXT_COLOR}; border:1px solid #2A2A2A; "
    f"border-radius:4px; padding:6px 10px; font-size:12px;"
)
_INPUT_FOCUS = f"background:#0C0C0C; color:{TEXT_COLOR}; border:1px solid {ACCENT_COLOR}; border-radius:4px; padding:6px 10px; font-size:12px;"


def _draw_key_icon(size: int = 64) -> QPixmap:
    """Disegna un'icona chiave vettoriale con QPainter."""
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    s = size
    # Testa chiave: cerchio con buco
    ring_r  = s * 0.28
    ring_cx = s * 0.35
    ring_cy = s * 0.35
    ring_w  = s * 0.09

    from PyQt6.QtGui import QPen
    from PyQt6.QtCore import QRectF

    pen = QPen(QColor(ACCENT_COLOR), ring_w)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(QRectF(ring_cx - ring_r, ring_cy - ring_r, ring_r * 2, ring_r * 2))

    # Gambo chiave (linea diagonale)
    pen2 = QPen(QColor(ACCENT_COLOR), ring_w)
    pen2.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen2)
    shaft_x1 = ring_cx + ring_r * 0.72
    shaft_y1 = ring_cy + ring_r * 0.72
    shaft_x2 = s * 0.82
    shaft_y2 = s * 0.82
    p.drawLine(int(shaft_x1), int(shaft_y1), int(shaft_x2), int(shaft_y2))

    # Dentini chiave
    tooth_len = s * 0.12
    for i, frac in enumerate([0.35, 0.58]):
        dx = shaft_x2 - shaft_x1
        dy = shaft_y2 - shaft_y1
        import math
        length = math.sqrt(dx * dx + dy * dy)
        ux, uy = dx / length, dy / length
        # Perpendicolare
        px2 = shaft_x1 + frac * dx - uy * tooth_len
        py2 = shaft_y1 + frac * dy + ux * tooth_len
        px1 = shaft_x1 + frac * dx
        py1 = shaft_y1 + frac * dy
        p.drawLine(int(px1), int(py1), int(px2), int(py2))

    p.end()
    return px


class SSHAuthDialog(QDialog):
    """
    Dialogo di autenticazione SSH con:
    - Icona chiave
    - Header con host:porta
    - Lista credenziali salvate
    - Form utente/password
    - Checkbox "ricorda"
    """

    def __init__(self, conn: "ConnectionInfo", parent=None):
        super().__init__(parent)
        self.conn = conn
        proto = conn.protocol.value if hasattr(conn.protocol, "value") else "SSH"
        self.setWindowTitle(f"Autenticazione — {conn.hostname}")
        self.setFixedSize(420, 560)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowCloseButtonHint
        )

        # Risultato
        self.result_username: str = conn.username or ""
        self.result_password: str = ""

        self._proto_label = proto
        self._build_ui()
        self._load_saved_creds()

        # Pre-carica password se salvata
        from core.crypto import decrypt
        if conn.password:
            self._pass_edit.setText(decrypt(conn.password))

    # ── UI ──────────────────────────────────────────────────

    def _build_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background: #111111;
                border: 1px solid #2A2A2A;
                border-radius: 8px;
            }}
            QLabel {{ background: transparent; color: {TEXT_COLOR}; }}
            QLineEdit {{
                {_INPUT}
                min-height: 32px;
            }}
            QLineEdit:focus {{ border-color: {ACCENT_COLOR}; }}
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # ── Header colorato ──
        header = QWidget()
        header.setFixedHeight(110)
        header.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            f"stop:0 #1A2A1A, stop:1 #111111);"
            f"border-bottom: 1px solid #2A2A2A;"
        )
        h_lay = QVBoxLayout(header)
        h_lay.setContentsMargins(20, 14, 20, 14)
        h_lay.setSpacing(4)

        # Icona + titolo
        top_row = QHBoxLayout()
        key_px = _draw_key_icon(44)
        key_lbl = QLabel()
        key_lbl.setPixmap(key_px)
        key_lbl.setFixedSize(44, 44)
        top_row.addWidget(key_lbl)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        t1 = QLabel("Autenticazione richiesta")
        t1.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        t1.setStyleSheet(f"color:{ACCENT_COLOR};")
        title_col.addWidget(t1)

        proto_str = self._proto_label
        host_str  = f"{self.conn.hostname}:{self.conn.port}"
        t2 = QLabel(f"{proto_str}  ·  {host_str}")
        t2.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px;")
        title_col.addWidget(t2)

        top_row.addLayout(title_col)
        top_row.addStretch()
        h_lay.addLayout(top_row)
        layout.addWidget(header)

        # ── Corpo ──
        body = QWidget()
        body.setStyleSheet("background:#111111;")
        b_lay = QVBoxLayout(body)
        b_lay.setContentsMargins(20, 16, 20, 16)
        b_lay.setSpacing(12)

        # Credenziali salvate
        saved_lbl = QLabel("Credenziali salvate:")
        saved_lbl.setStyleSheet(f"color:{SUB_COLOR}; font-size:10px; font-weight:bold; letter-spacing:1px;")
        b_lay.addWidget(saved_lbl)

        self._cred_list = QListWidget()
        self._cred_list.setFixedHeight(100)
        self._cred_list.setStyleSheet(f"""
            QListWidget {{
                background:#0A0A0A; color:{TEXT_COLOR};
                border:1px solid #2A2A2A; border-radius:4px; font-size:12px;
                outline:none;
            }}
            QListWidget::item {{ padding:5px 10px; }}
            QListWidget::item:selected {{ background:{ACCENT_COLOR}; color:white; }}
            QListWidget::item:hover:!selected {{ background:#1A1A1A; }}
        """)
        self._cred_list.itemClicked.connect(self._on_cred_pick)
        b_lay.addWidget(self._cred_list)

        # Separatore
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("border:1px solid #1E1E1E;")
        b_lay.addWidget(sep)

        # Form
        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        def lbl(txt):
            l = QLabel(txt)
            l.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px;")
            return l

        self._user_edit = QLineEdit(self.conn.username or "")
        self._user_edit.setPlaceholderText("username")
        self._user_edit.returnPressed.connect(lambda: self._pass_edit.setFocus())
        form.addRow(lbl("Utente:"), self._user_edit)

        self._pass_edit = QLineEdit()
        self._pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._pass_edit.setPlaceholderText("password")
        self._pass_edit.returnPressed.connect(self._on_connect)
        form.addRow(lbl("Password:"), self._pass_edit)

        b_lay.addLayout(form)

        # Checkbox
        self._remember_cb = QCheckBox("Ricorda la password per questa connessione")
        self._remember_cb.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px;")
        self._remember_cb.setChecked(bool(self.conn.password))
        b_lay.addWidget(self._remember_cb)

        self._save_cred_cb = QCheckBox("Salva nelle credenziali condivise")
        self._save_cred_cb.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px;")
        b_lay.addWidget(self._save_cred_cb)

        b_lay.addStretch()

        # Bottoni
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        cancel_btn = QPushButton("Annulla")
        cancel_btn.setFixedHeight(36)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{ background:#1E1E1E; color:{TEXT_COLOR}; border:1px solid #333;
                          border-radius:4px; padding:0 18px; font-size:12px; }}
            QPushButton:hover {{ background:#2A2A2A; }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        connect_btn = QPushButton("  ▶  Connetti")
        connect_btn.setFixedHeight(36)
        connect_btn.setDefault(True)
        connect_btn.setStyleSheet(f"""
            QPushButton {{ background:{ACCENT_COLOR}; color:white; border:none;
                          border-radius:4px; padding:0 22px;
                          font-size:12px; font-weight:bold; }}
            QPushButton:hover {{ background:#0088DD; }}
            QPushButton:pressed {{ background:#005A9E; }}
        """)
        connect_btn.clicked.connect(self._on_connect)
        btn_row.addWidget(connect_btn)

        b_lay.addLayout(btn_row)
        layout.addWidget(body)

    # ── Logica ──────────────────────────────────────────────

    def _load_saved_creds(self):
        self._cred_list.clear()
        try:
            from core.credentials import CredentialManager
            creds = CredentialManager.get_instance().all()
        except Exception:
            creds = []

        if self.conn.username:
            item = QListWidgetItem(f"  🔑  Connessione  [{self.conn.username}]")
            item.setData(Qt.ItemDataRole.UserRole, None)
            item.setForeground(QColor(SUB_COLOR))
            self._cred_list.addItem(item)

        for cred in creds:
            text = f"  👤  {cred.name}  |  {cred.username}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, cred)
            self._cred_list.addItem(item)

        if self._cred_list.count() == 0:
            item = QListWidgetItem("  Nessuna credenziale salvata")
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            item.setForeground(QColor("#444"))
            self._cred_list.addItem(item)

    def _on_cred_pick(self, item: QListWidgetItem):
        cred = item.data(Qt.ItemDataRole.UserRole)
        if cred is None:
            self._user_edit.setText(self.conn.username or "")
            from core.crypto import decrypt
            self._pass_edit.setText(decrypt(self.conn.password) if self.conn.password else "")
        else:
            self._user_edit.setText(cred.username)
            self._pass_edit.setText(cred.get_password())

    def _on_connect(self):
        username = self._user_edit.text().strip()
        password = self._pass_edit.text()

        if not username:
            self._user_edit.setFocus()
            self._user_edit.setStyleSheet(_INPUT_FOCUS)
            return

        self.result_username = username
        self.result_password = password

        # Ricorda password nella connessione
        if self._remember_cb.isChecked():
            try:
                from core.crypto import encrypt
                self.conn.username = username
                self.conn.password = encrypt(password)
            except Exception:
                pass

        # Salva nelle credenziali condivise
        if self._save_cred_cb.isChecked() and password:
            try:
                from core.credentials import CredentialManager
                CredentialManager.get_instance().add(
                    name=f"{username}@{self.conn.hostname}",
                    username=username,
                    password=password,
                )
            except Exception:
                pass

        self.accept()
