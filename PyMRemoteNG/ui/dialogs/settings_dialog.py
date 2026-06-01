"""
Dialog Impostazioni — configurazione app, protocolli, SSH, aspetto.
"""
import json, os
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTabWidget, QWidget, QFormLayout, QCheckBox,
    QSpinBox, QComboBox, QGroupBox, QFileDialog, QDialogButtonBox,
    QFrame
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from themes.dark_theme import ACCENT_COLOR, CARD_COLOR, TEXT_COLOR, SUB_COLOR, BG_COLOR

SETTINGS_PATH = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "PyMRemoteNG", "settings.json"
)


def load_settings() -> dict:
    try:
        with open(SETTINGS_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(data: dict):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _group(title: str) -> tuple:
    box = QGroupBox(title)
    box.setStyleSheet(f"""
        QGroupBox {{ color: {SUB_COLOR}; border: 1px solid #2A2A2A;
            border-radius: 3px; margin-top: 10px; padding-top: 8px; font-weight: bold; }}
        QGroupBox::title {{ subcontrol-origin: margin; padding: 0 6px; }}
    """)
    form = QFormLayout(box)
    form.setSpacing(8); form.setContentsMargins(12,14,12,10)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
    return box, form


def _inp(text=""):
    w = QLineEdit(text)
    w.setStyleSheet(f"background:#1E1E1E; color:{TEXT_COLOR}; border:1px solid #333; border-radius:3px; padding:4px 8px;")
    return w


def _lbl(t):
    l = QLabel(t); l.setStyleSheet(f"color:{SUB_COLOR}; background:transparent;")
    return l


def _spin(val=0, mn=0, mx=9999):
    s = QSpinBox(); s.setValue(val); s.setRange(mn, mx)
    s.setStyleSheet(f"background:#1E1E1E; color:{TEXT_COLOR}; border:1px solid #333; border-radius:3px; padding:2px;")
    return s


def _combo(opts, cur=""):
    c = QComboBox(); c.addItems(opts)
    if cur in opts: c.setCurrentText(cur)
    c.setStyleSheet(f"""
        QComboBox {{ background:#1E1E1E; color:{TEXT_COLOR}; border:1px solid #333; border-radius:3px; padding:3px 6px; }}
        QComboBox QAbstractItemView {{ background:#1E1E1E; color:{TEXT_COLOR}; selection-background-color:{ACCENT_COLOR}; }}
    """)
    return c


def _check(label, checked=False):
    cb = QCheckBox(label); cb.setChecked(checked)
    cb.setStyleSheet(f"color:{TEXT_COLOR};")
    return cb


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙  Impostazioni PyMRemoteNG")
        self.setMinimumSize(560, 520)
        self.setStyleSheet(f"QDialog {{ background:{CARD_COLOR}; color:{TEXT_COLOR}; }}")
        self._cfg = load_settings()
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{ background:{CARD_COLOR}; border:none; }}
            QTabBar::tab {{ background:#141414; color:{SUB_COLOR}; padding:7px 16px; border:none; margin-right:1px; }}
            QTabBar::tab:selected {{ background:{CARD_COLOR}; color:{TEXT_COLOR}; border-bottom:2px solid {ACCENT_COLOR}; }}
            QTabBar::tab:hover:!selected {{ background:#1E1E1E; }}
        """)
        self.tabs.addTab(self._tab_appearance(),  "🎨  Aspetto")
        self.tabs.addTab(self._tab_ssh(),          "🔑  SSH")
        self.tabs.addTab(self._tab_rdp(),          "🖥  RDP")
        self.tabs.addTab(self._tab_general(),      "⚙  Generale")
        layout.addWidget(self.tabs)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.setStyleSheet(f"""
            QDialogButtonBox {{ background:#141414; border-top:1px solid #2A2A2A; padding:8px; }}
            QPushButton {{ background:#2D2D2D; color:{TEXT_COLOR}; border:1px solid #333;
                border-radius:3px; padding:5px 18px; min-width:80px; }}
            QPushButton:hover {{ background:#3D3D3D; }}
            QPushButton[text="OK"] {{ background:{ACCENT_COLOR}; border-color:{ACCENT_COLOR}; color:white; }}
        """)
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    # ── Tab Aspetto ──
    def _tab_appearance(self) -> QWidget:
        w = QWidget(); vl = QVBoxLayout(w); vl.setContentsMargins(16,16,16,16)

        box, form = _group("Tema e Font")
        self.f_theme      = _combo(["Dark (default)", "Light", "High Contrast"], "Dark (default)")
        self.f_font_size  = _spin(12, 8, 24)
        self.f_term_font  = _combo(["Cascadia Code", "Consolas", "Courier New", "Fira Code", "JetBrains Mono"], "Cascadia Code")
        self.f_term_size  = _spin(13, 8, 28)
        form.addRow(_lbl("Tema UI:"),         self.f_theme)
        form.addRow(_lbl("Font UI (pt):"),    self.f_font_size)
        form.addRow(_lbl("Font terminale:"),  self.f_term_font)
        form.addRow(_lbl("Dim terminale:"),   self.f_term_size)
        vl.addWidget(box)

        box2, form2 = _group("Tab e Sessioni")
        self.f_tab_color    = _check("Colora tabs per protocollo", True)
        self.f_confirm_close = _check("Chiedi conferma prima di chiudere sessioni", True)
        self.f_restore_sess = _check("Ripristina sessioni all'avvio", False)
        form2.addRow("", self.f_tab_color)
        form2.addRow("", self.f_confirm_close)
        form2.addRow("", self.f_restore_sess)
        vl.addWidget(box2)
        vl.addStretch()
        return w

    # ── Tab SSH ──
    def _tab_ssh(self) -> QWidget:
        w = QWidget(); vl = QVBoxLayout(w); vl.setContentsMargins(16,16,16,16)

        box, form = _group("Autenticazione SSH")
        self.f_ssh_key_path  = _inp()
        self.f_ssh_key_path.setPlaceholderText("~/.ssh/id_rsa")
        browse_btn = QPushButton("...")
        browse_btn.setFixedWidth(32)
        browse_btn.setStyleSheet(f"background:#2A2A2A; color:{TEXT_COLOR}; border:1px solid #333; border-radius:3px;")
        browse_btn.clicked.connect(self._browse_key)
        key_row = QHBoxLayout(); key_row.addWidget(self.f_ssh_key_path); key_row.addWidget(browse_btn)
        key_widget = QWidget(); key_widget.setLayout(key_row); key_widget.setStyleSheet("background:transparent;")
        form.addRow(_lbl("Chiave privata:"), key_widget)

        self.f_ssh_timeout   = _spin(15, 1, 120)
        self.f_ssh_keepalive = _spin(60, 0, 3600)
        self.f_ssh_compress  = _check("Compressione SSH")
        self.f_ssh_agent     = _check("Usa SSH agent (se disponibile)", True)
        self.f_ssh_term      = _combo(["xterm-256color", "xterm", "vt100", "linux"], "xterm-256color")
        form.addRow(_lbl("Timeout (sec):"),    self.f_ssh_timeout)
        form.addRow(_lbl("Keepalive (sec):"),  self.f_ssh_keepalive)
        form.addRow(_lbl("Tipo terminale:"),   self.f_ssh_term)
        form.addRow("", self.f_ssh_compress)
        form.addRow("", self.f_ssh_agent)
        vl.addWidget(box)

        box2, form2 = _group("Trasferimento file (SFTP)")
        self.f_sftp_dir = _inp()
        self.f_sftp_dir.setPlaceholderText(os.path.expanduser("~"))
        form2.addRow(_lbl("Download dir:"), self.f_sftp_dir)
        vl.addWidget(box2)
        vl.addStretch()
        return w

    def _browse_key(self):
        path, _ = QFileDialog.getOpenFileName(self, "Seleziona chiave SSH",
                                              os.path.expanduser("~/.ssh"), "All Files (*)")
        if path: self.f_ssh_key_path.setText(path)

    # ── Tab RDP ──
    def _tab_rdp(self) -> QWidget:
        w = QWidget(); vl = QVBoxLayout(w); vl.setContentsMargins(16,16,16,16)

        box, form = _group("Default RDP")
        self.f_rdp_version = _combo(["Rdc10","Rdc11","Rdc9","Rdc8","Rdc7"], "Rdc10")
        self.f_rdp_colors  = _combo(["Colors32Bit","Colors24Bit","Colors16Bit"], "Colors32Bit")
        self.f_rdp_cred    = _check("Usa CredSSP", True)
        self.f_rdp_clip    = _check("Reindirizza appunti", True)
        form.addRow(_lbl("Versione RDP:"),  self.f_rdp_version)
        form.addRow(_lbl("Colori:"),        self.f_rdp_colors)
        form.addRow("", self.f_rdp_cred)
        form.addRow("", self.f_rdp_clip)
        vl.addWidget(box)
        vl.addStretch()
        return w

    # ── Tab Generale ──
    def _tab_general(self) -> QWidget:
        w = QWidget(); vl = QVBoxLayout(w); vl.setContentsMargins(16,16,16,16)

        box, form = _group("Salvataggio")
        self.f_autosave    = _check("Salvataggio automatico connessioni", True)
        self.f_autosave_int = _spin(5, 1, 60)
        self.f_backup      = _check("Crea backup prima di salvare", True)
        form.addRow("", self.f_autosave)
        form.addRow(_lbl("Intervallo (min):"), self.f_autosave_int)
        form.addRow("", self.f_backup)
        vl.addWidget(box)

        box2, form2 = _group("Aggiornamenti")
        self.f_check_updates = _check("Controlla aggiornamenti all'avvio", False)
        form2.addRow("", self.f_check_updates)
        vl.addWidget(box2)
        vl.addStretch()
        return w

    # ── Carica / Salva ──
    def _load(self):
        c = self._cfg
        if "font_size"      in c: self.f_font_size.setValue(c["font_size"])
        if "term_font"      in c: self.f_term_font.setCurrentText(c["term_font"])
        if "term_size"      in c: self.f_term_size.setValue(c["term_size"])
        if "ssh_key_path"   in c: self.f_ssh_key_path.setText(c["ssh_key_path"])
        if "ssh_timeout"    in c: self.f_ssh_timeout.setValue(c["ssh_timeout"])
        if "ssh_keepalive"  in c: self.f_ssh_keepalive.setValue(c["ssh_keepalive"])
        if "ssh_term"       in c: self.f_ssh_term.setCurrentText(c["ssh_term"])
        if "ssh_agent"      in c: self.f_ssh_agent.setChecked(c["ssh_agent"])
        if "ssh_compress"   in c: self.f_ssh_compress.setChecked(c["ssh_compress"])
        if "autosave"       in c: self.f_autosave.setChecked(c["autosave"])
        if "autosave_int"   in c: self.f_autosave_int.setValue(c["autosave_int"])

    def _on_ok(self):
        cfg = {
            "font_size":    self.f_font_size.value(),
            "term_font":    self.f_term_font.currentText(),
            "term_size":    self.f_term_size.value(),
            "ssh_key_path": self.f_ssh_key_path.text(),
            "ssh_timeout":  self.f_ssh_timeout.value(),
            "ssh_keepalive":self.f_ssh_keepalive.value(),
            "ssh_term":     self.f_ssh_term.currentText(),
            "ssh_agent":    self.f_ssh_agent.isChecked(),
            "ssh_compress": self.f_ssh_compress.isChecked(),
            "rdp_version":  self.f_rdp_version.currentText(),
            "rdp_colors":   self.f_rdp_colors.currentText(),
            "autosave":     self.f_autosave.isChecked(),
            "autosave_int": self.f_autosave_int.value(),
        }
        save_settings(cfg)
        self.accept()
