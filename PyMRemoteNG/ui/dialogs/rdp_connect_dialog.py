"""
Dialogo di connessione RDP completo:
- Credenziali (con saved credentials)
- Reindirizzamento (clipboard, dischi, stampanti, audio, ecc.)
- Display (risoluzione, colori)
Sostituisce CredentialPickerDialog per RDP, evitando i dialoghi Windows.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QCheckBox, QComboBox, QTabWidget, QWidget,
    QListWidget, QListWidgetItem, QFrame, QFormLayout,
    QGroupBox, QSpinBox, QRadioButton, QButtonGroup
)
from themes.dark_theme import ACCENT_COLOR, TEXT_COLOR, SUB_COLOR, BG_COLOR

if TYPE_CHECKING:
    from core.models import ConnectionInfo

_INPUT = (
    f"background:#111111; color:{TEXT_COLOR}; border:1px solid #252525; "
    f"border-radius:4px; padding:5px 10px; font-size:12px;"
)
_GROUP = (
    f"QGroupBox {{ color:{SUB_COLOR}; border:1px solid #1E1E1E; border-radius:5px; "
    f"margin-top:10px; padding:10px 8px 8px 8px; font-size:11px; }}"
    f"QGroupBox::title {{ subcontrol-origin:margin; padding:0 6px; "
    f"color:{SUB_COLOR}; background:{BG_COLOR}; }}"
)


@dataclass
class RDPOptions:
    """Risultato del dialogo: credenziali + opzioni."""
    username:    str = ""
    password:    str = ""
    domain:      str = ""
    # Reindirizzamento
    redirect_clipboard:    bool = True
    redirect_drives:       bool = False
    redirect_printers:     bool = False
    redirect_serial:       bool = False
    redirect_smartcard:    bool = False
    redirect_audio:        bool = False
    redirect_microphone:   bool = False
    # Display
    resolution:  str = "fullscreen"   # fullscreen | 1920x1080 | 1280x720 | 1024x768 | custom
    width:       int = 1920
    height:      int = 1080
    color_depth: int = 32
    # Avanzate
    use_nla:     bool = True
    disable_warning: bool = True


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("border:none; border-top:1px solid #1E1E1E; margin:2px 0;")
    return f


class RDPConnectDialog(QDialog):
    """
    Dialogo completo pre-connessione RDP.
    Restituisce un RDPOptions con tutte le impostazioni scelte.
    """

    def __init__(self, conn: "ConnectionInfo", parent=None):
        super().__init__(parent)
        self.conn = conn
        self.result_opts = RDPOptions()
        self.setWindowTitle(f"Connessione RDP — {conn.hostname}")
        self.setMinimumSize(500, 540)
        self.setStyleSheet(f"QDialog {{ background:{BG_COLOR}; color:{TEXT_COLOR}; }}")
        self._build_ui()
        self._load_saved_creds()
        self._populate_from_conn()

    # ── UI ──────────────────────────────────────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(56)
        hdr.setStyleSheet(
            "background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "stop:0 #0A1A2A,stop:1 #0D0D0D); border-bottom:1px solid #1A1A1A;"
        )
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(18, 0, 18, 0)
        icon = QLabel("🖥")
        icon.setStyleSheet("font-size:22px; background:transparent;")
        hl.addWidget(icon)
        tcol = QVBoxLayout()
        t1 = QLabel("Connessione Desktop Remoto")
        t1.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        t1.setStyleSheet(f"color:#4E9EEC; background:transparent;")
        tcol.addWidget(t1)
        t2 = QLabel(f"RDP  ·  {self.conn.hostname}:{self.conn.port or 3389}")
        t2.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px; background:transparent;")
        tcol.addWidget(t2)
        hl.addLayout(tcol)
        hl.addStretch()
        lay.addWidget(hdr)

        # Tab widget
        self._tabs = QTabWidget()
        self._tabs.setStyleSheet(f"""
            QTabWidget::pane {{ background:{BG_COLOR}; border:none; }}
            QTabBar::tab {{
                background:#111111; color:{SUB_COLOR}; padding:8px 18px;
                border:none; border-right:1px solid #1A1A1A; font-size:11px;
            }}
            QTabBar::tab:selected {{ background:{BG_COLOR}; color:{TEXT_COLOR};
                                     border-top:2px solid #4E9EEC; }}
            QTabBar::tab:hover:!selected {{ background:#161616; color:{TEXT_COLOR}; }}
        """)

        self._tabs.addTab(self._build_cred_tab(),     "🔑  Credenziali")
        self._tabs.addTab(self._build_redirect_tab(), "⇄  Reindirizzamento")
        self._tabs.addTab(self._build_display_tab(),  "🖥  Display")

        lay.addWidget(self._tabs)

        # Footer bottoni
        footer = QWidget()
        footer.setFixedHeight(54)
        footer.setStyleSheet("background:#0D0D0D; border-top:1px solid #1A1A1A;")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(18, 0, 18, 0)
        fl.setSpacing(8)
        fl.addStretch()

        cancel_btn = QPushButton("Annulla")
        cancel_btn.setFixedHeight(34)
        cancel_btn.setStyleSheet(
            f"QPushButton {{ background:#1A1A1A; color:{TEXT_COLOR}; border:1px solid #2A2A2A;"
            f" border-radius:4px; padding:0 18px; }}"
            f"QPushButton:hover {{ background:#222222; }}"
        )
        cancel_btn.clicked.connect(self.reject)
        fl.addWidget(cancel_btn)

        connect_btn = QPushButton("  ▶  Connetti")
        connect_btn.setFixedHeight(34)
        connect_btn.setDefault(True)
        connect_btn.setStyleSheet(f"""
            QPushButton {{ background:#4E9EEC; color:white; border:none;
                          border-radius:4px; padding:0 24px;
                          font-size:12px; font-weight:bold; }}
            QPushButton:hover {{ background:#5BAAEE; }}
            QPushButton:pressed {{ background:#3A8ADA; }}
        """)
        connect_btn.clicked.connect(self._on_connect)
        fl.addWidget(connect_btn)
        lay.addWidget(footer)

    # ── Tab Credenziali ──────────────────────────────────────────────

    def _build_cred_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{BG_COLOR};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(10)

        # Credenziali salvate
        saved_lbl = QLabel("Credenziali salvate:")
        saved_lbl.setStyleSheet(f"color:{SUB_COLOR}; font-size:10px; font-weight:bold;")
        lay.addWidget(saved_lbl)

        self._cred_list = QListWidget()
        self._cred_list.setFixedHeight(90)
        self._cred_list.setStyleSheet(f"""
            QListWidget {{ background:#0A0A0A; color:{TEXT_COLOR};
                           border:1px solid #1E1E1E; border-radius:4px; outline:none; }}
            QListWidget::item {{ padding:5px 10px; }}
            QListWidget::item:selected {{ background:#4E9EEC; color:white; }}
            QListWidget::item:hover:!selected {{ background:#141414; }}
        """)
        self._cred_list.itemClicked.connect(self._on_cred_pick)
        lay.addWidget(self._cred_list)

        lay.addWidget(_sep())

        form = QFormLayout()
        form.setSpacing(8)

        def lbl(t):
            l = QLabel(t)
            l.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px; background:transparent;")
            return l

        self._user_edit = QLineEdit()
        self._user_edit.setStyleSheet(_INPUT)
        self._user_edit.setPlaceholderText("es. amministratore")
        self._user_edit.returnPressed.connect(lambda: self._pass_edit.setFocus())
        form.addRow(lbl("Utente:"), self._user_edit)

        self._pass_edit = QLineEdit()
        self._pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._pass_edit.setStyleSheet(_INPUT)
        self._pass_edit.setPlaceholderText("password")
        self._pass_edit.returnPressed.connect(self._on_connect)
        form.addRow(lbl("Password:"), self._pass_edit)

        self._domain_edit = QLineEdit()
        self._domain_edit.setStyleSheet(_INPUT)
        self._domain_edit.setPlaceholderText("es. AZIENDA  (opzionale)")
        form.addRow(lbl("Dominio:"), self._domain_edit)

        lay.addLayout(form)

        self._remember_cb = QCheckBox("Ricorda queste credenziali per la connessione")
        self._remember_cb.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px; background:transparent;")
        lay.addWidget(self._remember_cb)

        self._save_cb = QCheckBox("Salva nelle credenziali condivise del vault")
        self._save_cb.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px; background:transparent;")
        lay.addWidget(self._save_cb)

        lay.addStretch()
        return w

    # ── Tab Reindirizzamento ─────────────────────────────────────────

    def _build_redirect_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{BG_COLOR};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(10)

        info = QLabel(
            "Scegli quali risorse locali rendere disponibili nella sessione remota.\n"
            "Queste impostazioni vengono applicate direttamente — nessun dialogo Windows."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px; background:transparent;")
        lay.addWidget(info)
        lay.addWidget(_sep())

        # Dispositivi locali
        dev_grp = QGroupBox("Dispositivi e risorse locali")
        dev_grp.setStyleSheet(_GROUP)
        dev_lay = QVBoxLayout(dev_grp)
        dev_lay.setSpacing(6)

        self._cb_clipboard = self._check("📋  Appunti  (copia/incolla tra locale e remoto)", True)
        self._cb_drives    = self._check("💾  Dischi fissi  (C:\\ D:\\ ecc.)", False)
        self._cb_printers  = self._check("🖨  Stampanti  (stampa dal remoto alla locale)", False)
        self._cb_serial    = self._check("🔌  Porte seriali  (COM1, COM2…)", False)
        self._cb_smartcard = self._check("💳  Smart Card", False)

        for cb in [self._cb_clipboard, self._cb_drives, self._cb_printers,
                   self._cb_serial, self._cb_smartcard]:
            dev_lay.addWidget(cb)
        lay.addWidget(dev_grp)

        # Audio
        audio_grp = QGroupBox("Audio e registrazione")
        audio_grp.setStyleSheet(_GROUP)
        audio_lay = QVBoxLayout(audio_grp)
        audio_lay.setSpacing(6)

        self._cb_audio = self._check("🔊  Riproduci audio del computer remoto qui", False)
        self._cb_mic   = self._check("🎙  Registrazione audio (microfono locale → remoto)", False)
        audio_lay.addWidget(self._cb_audio)
        audio_lay.addWidget(self._cb_mic)
        lay.addWidget(audio_grp)

        lay.addStretch()
        return w

    # ── Tab Display ──────────────────────────────────────────────────

    def _build_display_tab(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{BG_COLOR};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(10)

        # Risoluzione
        res_grp = QGroupBox("Risoluzione schermo")
        res_grp.setStyleSheet(_GROUP)
        res_lay = QVBoxLayout(res_grp)
        res_lay.setSpacing(6)

        self._res_bg = QButtonGroup(self)
        presets = [
            ("Schermo intero  (consigliato)",   "fullscreen"),
            ("1920 × 1080",                      "1920x1080"),
            ("1280 × 720",                       "1280x720"),
            ("1024 × 768",                       "1024x768"),
            ("Personalizzata",                   "custom"),
        ]
        for i, (label, val) in enumerate(presets):
            rb = QRadioButton(label)
            rb.setStyleSheet(f"color:{TEXT_COLOR}; background:transparent;")
            rb.setProperty("res_val", val)
            if i == 0:
                rb.setChecked(True)
            self._res_bg.addButton(rb, i)
            res_lay.addWidget(rb)
            if val == "custom":
                custom_row = QHBoxLayout()
                self._w_spin = QSpinBox()
                self._w_spin.setRange(640, 7680)
                self._w_spin.setValue(1280)
                self._w_spin.setFixedWidth(80)
                self._w_spin.setStyleSheet(_INPUT)
                self._h_spin = QSpinBox()
                self._h_spin.setRange(480, 4320)
                self._h_spin.setValue(720)
                self._h_spin.setFixedWidth(80)
                self._h_spin.setStyleSheet(_INPUT)
                lx = QLabel("×")
                lx.setStyleSheet(f"color:{SUB_COLOR}; background:transparent;")
                custom_row.addSpacing(20)
                custom_row.addWidget(self._w_spin)
                custom_row.addWidget(lx)
                custom_row.addWidget(self._h_spin)
                custom_row.addStretch()
                res_lay.addLayout(custom_row)
        lay.addWidget(res_grp)

        # Profondità colore
        col_grp = QGroupBox("Qualità colori")
        col_grp.setStyleSheet(_GROUP)
        col_lay = QHBoxLayout(col_grp)
        col_lbl = QLabel("Profondità colore:")
        col_lbl.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px; background:transparent;")
        col_lay.addWidget(col_lbl)
        self._color_combo = QComboBox()
        self._color_combo.setStyleSheet(_INPUT)
        self._color_combo.addItems(["32 bit (Alta qualità)", "24 bit", "16 bit", "15 bit"])
        self._color_combo.setFixedWidth(180)
        col_lay.addWidget(self._color_combo)
        col_lay.addStretch()
        lay.addWidget(col_grp)

        # Opzioni sicurezza
        sec_grp = QGroupBox("Sicurezza e autenticazione")
        sec_grp.setStyleSheet(_GROUP)
        sec_lay = QVBoxLayout(sec_grp)
        self._nla_cb = self._check(
            "Usa autenticazione NLA (Network Level Authentication)", True
        )
        self._no_warn_cb = self._check(
            "Non mostrare avvisi di sicurezza per certificati sconosciuti", True
        )
        sec_lay.addWidget(self._nla_cb)
        sec_lay.addWidget(self._no_warn_cb)
        lay.addWidget(sec_grp)

        lay.addStretch()
        return w

    # ── Helpers ──────────────────────────────────────────────────────

    def _check(self, label: str, checked: bool = False) -> QCheckBox:
        cb = QCheckBox(label)
        cb.setChecked(checked)
        cb.setStyleSheet(f"color:{TEXT_COLOR}; background:transparent; font-size:12px;")
        return cb

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

        for c in creds:
            item = QListWidgetItem(f"  👤  {c.name}  |  {c.username}")
            item.setData(Qt.ItemDataRole.UserRole, c)
            self._cred_list.addItem(item)

        if self._cred_list.count() == 0:
            placeholder = QListWidgetItem("  Nessuna credenziale salvata")
            placeholder.setFlags(Qt.ItemFlag.NoItemFlags)
            placeholder.setForeground(QColor("#444"))
            self._cred_list.addItem(placeholder)

    def _populate_from_conn(self):
        """Pre-compila campi con i valori salvati nella connessione."""
        self._user_edit.setText(self.conn.username or "")
        if self.conn.domain:
            self._domain_edit.setText(self.conn.domain)
        from core.crypto import decrypt
        if self.conn.password:
            self._pass_edit.setText(decrypt(self.conn.password))
            self._remember_cb.setChecked(True)
        # Redirect flags dalla connessione
        self._cb_clipboard.setChecked(getattr(self.conn, "redirect_clipboard", True))
        self._cb_drives.setChecked(getattr(self.conn, "redirect_drives", "") not in ("None", "", False))
        self._cb_printers.setChecked(getattr(self.conn, "redirect_printers", False))
        self._cb_serial.setChecked(getattr(self.conn, "redirect_ports", False))
        self._cb_smartcard.setChecked(getattr(self.conn, "redirect_smart_cards", False))

    def _on_cred_pick(self, item: QListWidgetItem):
        cred = item.data(Qt.ItemDataRole.UserRole)
        if cred is None:
            self._user_edit.setText(self.conn.username or "")
            from core.crypto import decrypt
            self._pass_edit.setText(decrypt(self.conn.password) if self.conn.password else "")
            self._domain_edit.setText(self.conn.domain or "")
        else:
            self._user_edit.setText(cred.username)
            self._pass_edit.setText(cred.get_password())
            self._domain_edit.setText(cred.domain or "")

    def _on_connect(self):
        username = self._user_edit.text().strip()
        if not username:
            self._user_edit.setFocus()
            self._user_edit.setStyleSheet(
                _INPUT.replace("#252525", ACCENT_COLOR)
            )
            return

        opts = RDPOptions()
        opts.username = username
        opts.password = self._pass_edit.text()
        opts.domain   = self._domain_edit.text().strip()

        # Redirect
        opts.redirect_clipboard  = self._cb_clipboard.isChecked()
        opts.redirect_drives     = self._cb_drives.isChecked()
        opts.redirect_printers   = self._cb_printers.isChecked()
        opts.redirect_serial     = self._cb_serial.isChecked()
        opts.redirect_smartcard  = self._cb_smartcard.isChecked()
        opts.redirect_audio      = self._cb_audio.isChecked()
        opts.redirect_microphone = self._cb_mic.isChecked()

        # Resolution
        checked_rb = self._res_bg.checkedButton()
        opts.resolution = checked_rb.property("res_val") if checked_rb else "fullscreen"
        if opts.resolution == "custom":
            opts.width  = self._w_spin.value()
            opts.height = self._h_spin.value()
        else:
            mapping = {"1920x1080": (1920,1080), "1280x720": (1280,720), "1024x768": (1024,768)}
            opts.width, opts.height = mapping.get(opts.resolution, (1920,1080))

        opts.color_depth     = [32, 24, 16, 15][self._color_combo.currentIndex()]
        opts.use_nla         = self._nla_cb.isChecked()
        opts.disable_warning = self._no_warn_cb.isChecked()

        # Salva credenziali
        if self._remember_cb.isChecked():
            try:
                from core.crypto import encrypt
                self.conn.username = username
                self.conn.password = encrypt(opts.password)
                self.conn.domain   = opts.domain
            except Exception:
                pass
        if self._save_cb.isChecked() and opts.password:
            try:
                from core.credentials import CredentialManager
                CredentialManager.get_instance().add(
                    name=f"{username}@{self.conn.hostname}",
                    username=username, password=opts.password,
                    domain=opts.domain,
                )
            except Exception:
                pass

        self.result_opts = opts
        self.accept()
