"""
Dialogo Nuova/Modifica Connessione - equivalente di ConfigWindow + PropertiesGrid.
Mostra tutte le proprietà organizzate in tab per categoria.
"""
from __future__ import annotations
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QComboBox, QCheckBox, QSpinBox,
    QDialogButtonBox, QFormLayout, QGroupBox, QScrollArea,
    QFrame, QPushButton, QGridLayout
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from themes.dark_theme import ACCENT_COLOR, CARD_COLOR, TEXT_COLOR, SUB_COLOR


def _form_group(title: str) -> tuple[QGroupBox, QFormLayout]:
    box = QGroupBox(title)
    box.setStyleSheet(f"""
        QGroupBox {{
            color: {SUB_COLOR};
            border: 1px solid #2A2A2A;
            border-radius: 4px;
            margin-top: 12px;
            padding-top: 8px;
            font-weight: bold;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 6px;
        }}
    """)
    form = QFormLayout(box)
    form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
    form.setFormAlignment(Qt.AlignmentFlag.AlignTop)
    form.setSpacing(9)
    form.setContentsMargins(14, 18, 14, 14)
    form.setHorizontalSpacing(12)
    return box, form


def _line_edit(text="") -> QLineEdit:
    w = QLineEdit(text)
    w.setStyleSheet(f"background: #1E1E1E; color: {TEXT_COLOR}; border: 1px solid #333; border-radius: 3px; padding: 4px 6px;")
    return w


def _password_edit(text="") -> QLineEdit:
    w = _line_edit(text)
    w.setEchoMode(QLineEdit.EchoMode.Password)
    return w


def _combo(options: list, current: str = "") -> QComboBox:
    cb = QComboBox()
    cb.addItems(options)
    cb.setStyleSheet(f"""
        QComboBox {{
            background: #1E1E1E;
            color: {TEXT_COLOR};
            border: 1px solid #333;
            border-radius: 3px;
            padding: 4px 6px;
        }}
        QComboBox QAbstractItemView {{
            background: #1E1E1E;
            color: {TEXT_COLOR};
            selection-background-color: {ACCENT_COLOR};
        }}
    """)
    if current in options:
        cb.setCurrentText(current)
    return cb


def _check(label: str, checked=False) -> QCheckBox:
    cb = QCheckBox(label)
    cb.setChecked(checked)
    cb.setStyleSheet(f"color: {TEXT_COLOR};")
    return cb


def _label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(f"color: {SUB_COLOR};")
    return lbl


class ConnectionDialog(QDialog):
    """Dialogo completo per creare/modificare una connessione."""

    def __init__(self, connection_info=None, parent=None):
        super().__init__(parent)
        from core.models import ConnectionInfo
        self._is_new = connection_info is None
        self.conn = connection_info or ConnectionInfo()
        self.setWindowTitle("Nuova Connessione" if self._is_new else f"Modifica: {self.conn.name}")
        self.setMinimumSize(640, 560)
        self.resize(700, 620)
        self.setModal(True)
        self.setStyleSheet(f"QDialog {{ background-color: {CARD_COLOR}; color: {TEXT_COLOR}; }}")
        self._setup_ui()
        self._load_data()
        self._update_tab_visibility(self.conn.protocol.value)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Tab widget
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet(f"""
            QTabWidget::pane {{
                background: {CARD_COLOR};
                border: none;
            }}
            QTabBar::tab {{
                background: #141414;
                color: {SUB_COLOR};
                padding: 7px 16px;
                border: none;
                margin-right: 1px;
            }}
            QTabBar::tab:selected {{
                background: {CARD_COLOR};
                color: {TEXT_COLOR};
                border-bottom: 2px solid {ACCENT_COLOR};
            }}
            QTabBar::tab:hover:!selected {{
                background: #1E1E1E;
            }}
        """)

        self.tabs.addTab(self._tab_general(), "🔌  Protocollo")
        self.tabs.addTab(self._tab_credentials(), "🔑  Credenziali")
        self.tabs.addTab(self._tab_rdp(), "🖥  RDP")
        self.tabs.addTab(self._tab_rdp_gateway(), "🌐  RD Gateway")
        self.tabs.addTab(self._tab_display(), "📺  Schermo")
        self.tabs.addTab(self._tab_redirect(), "↔  Redirect")
        self.tabs.addTab(self._tab_vnc(), "🖱  VNC")
        self.tabs.addTab(self._tab_misc(), "⚙  Altro")

        layout.addWidget(self.tabs)

        # Bottoni OK/Annulla
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.setStyleSheet(f"""
            QDialogButtonBox {{ background: #141414; border-top: 1px solid #2A2A2A; padding: 8px; }}
            QPushButton {{ background: #2D2D2D; color: {TEXT_COLOR}; border: 1px solid #333;
                          border-radius: 3px; padding: 5px 18px; min-width: 80px; }}
            QPushButton:hover {{ background: #3D3D3D; }}
            QPushButton[text="OK"] {{ background: {ACCENT_COLOR}; border-color: {ACCENT_COLOR}; color: white; }}
            QPushButton[text="OK"]:hover {{ background: #0088DD; }}
        """)
        btn_box.accepted.connect(self._on_accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    # ── Tab: Protocollo ──
    def _tab_general(self) -> QWidget:
        w = QScrollArea()
        w.setWidgetResizable(True)
        w.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        box, form = _form_group("Connessione")
        self.f_name     = _line_edit()
        self.f_desc     = _line_edit()
        self.f_hostname = _line_edit()
        self.f_port     = QSpinBox()
        self.f_port.setRange(1, 65535)
        self.f_port.setStyleSheet(f"background: #1E1E1E; color: {TEXT_COLOR}; border: 1px solid #333; border-radius: 3px; padding: 3px;")
        form.addRow(_label("Nome:"),     self.f_name)
        form.addRow(_label("Descrizione:"), self.f_desc)
        form.addRow(_label("Hostname / IP:"), self.f_hostname)
        form.addRow(_label("Porta:"),    self.f_port)
        layout.addWidget(box)

        box2, form2 = _form_group("Protocollo")
        from core.models import ProtocolType
        protos = [p.value for p in ProtocolType]
        self.f_protocol = _combo(protos, self.conn.protocol.value)
        self.f_protocol.currentTextChanged.connect(self._on_protocol_changed)
        form2.addRow(_label("Protocollo:"), self.f_protocol)
        self.f_panel = _line_edit()
        form2.addRow(_label("Pannello:"), self.f_panel)
        layout.addWidget(box2)

        layout.addStretch()
        w.setWidget(inner)
        return w

    # ── Tab: Credenziali ──
    def _tab_credentials(self) -> QWidget:
        w = QScrollArea()
        w.setWidgetResizable(True)
        w.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(20, 20, 20, 20)

        box, form = _form_group("Autenticazione")
        self.f_username = _line_edit()
        self.f_password = _password_edit()
        self.f_domain   = _line_edit()
        self.f_show_pw  = _check("Mostra password")
        self.f_show_pw.stateChanged.connect(
            lambda s: self.f_password.setEchoMode(
                QLineEdit.EchoMode.Normal if s else QLineEdit.EchoMode.Password))
        form.addRow(_label("Utente:"),   self.f_username)
        form.addRow(_label("Password:"), self.f_password)
        form.addRow("", self.f_show_pw)
        form.addRow(_label("Dominio:"),  self.f_domain)
        layout.addWidget(box)

        box2, form2 = _form_group("SSH")
        self.f_putty_session  = _line_edit()
        self.f_ssh_options    = _line_edit()
        self.f_opening_cmd    = _line_edit()
        self.f_ssh_tunnel     = _line_edit()
        form2.addRow(_label("Sessione PuTTY:"),  self.f_putty_session)
        form2.addRow(_label("SSH Options:"),     self.f_ssh_options)
        form2.addRow(_label("Comando apertura:"), self.f_opening_cmd)
        form2.addRow(_label("SSH Tunnel:"),      self.f_ssh_tunnel)
        layout.addWidget(box2)

        layout.addStretch()
        w.setWidget(inner)
        return w

    # ── Tab: RDP ──
    def _tab_rdp(self) -> QWidget:
        w = QScrollArea()
        w.setWidgetResizable(True)
        w.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(20, 20, 20, 20)

        box, form = _form_group("Opzioni RDP")
        from core.models import RDPAuthLevel
        rdp_versions = ["Rdc7", "Rdc8", "Rdc9", "Rdc10", "Rdc11"]
        auth_levels  = [a.value for a in RDPAuthLevel]
        self.f_rdp_version   = _combo(rdp_versions)
        self.f_rdp_auth      = _combo(auth_levels)
        self.f_use_console   = _check("Connetti alla sessione console")
        self.f_use_cred_ssp  = _check("Usa CredSSP")
        self.f_restricted_admin = _check("Restricted Admin")
        self.f_idle_timeout  = QSpinBox()
        self.f_idle_timeout.setRange(0, 240)
        self.f_idle_timeout.setSuffix(" min")
        self.f_idle_timeout.setStyleSheet(f"background: #1E1E1E; color: {TEXT_COLOR}; border: 1px solid #333; border-radius: 3px;")
        self.f_alert_idle    = _check("Alert idle timeout")
        self.f_load_balance  = _line_edit()
        self.f_start_program = _line_edit()
        self.f_start_workdir = _line_edit()
        form.addRow(_label("Versione RDP:"),      self.f_rdp_version)
        form.addRow(_label("Auth Level:"),        self.f_rdp_auth)
        form.addRow("", self.f_use_console)
        form.addRow("", self.f_use_cred_ssp)
        form.addRow("", self.f_restricted_admin)
        form.addRow(_label("Idle timeout:"),      self.f_idle_timeout)
        form.addRow("", self.f_alert_idle)
        form.addRow(_label("Load Balance Info:"), self.f_load_balance)
        form.addRow(_label("Programma avvio:"),   self.f_start_program)
        form.addRow(_label("Working dir:"),       self.f_start_workdir)
        layout.addWidget(box)
        layout.addStretch()
        w.setWidget(inner)
        return w

    # ── Tab: RD Gateway ──
    def _tab_rdp_gateway(self) -> QWidget:
        w = QScrollArea()
        w.setWidgetResizable(True)
        w.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(20, 20, 20, 20)

        box, form = _form_group("RD Gateway")
        from core.models import RDGatewayUsage
        usage_opts = [u.value for u in RDGatewayUsage]
        self.f_rdg_usage    = _combo(usage_opts)
        self.f_rdg_hostname = _line_edit()
        self.f_rdg_username = _line_edit()
        self.f_rdg_password = _password_edit()
        self.f_rdg_domain   = _line_edit()
        form.addRow(_label("Modalità:"),   self.f_rdg_usage)
        form.addRow(_label("Hostname:"),   self.f_rdg_hostname)
        form.addRow(_label("Utente:"),     self.f_rdg_username)
        form.addRow(_label("Password:"),   self.f_rdg_password)
        form.addRow(_label("Dominio:"),    self.f_rdg_domain)
        layout.addWidget(box)
        layout.addStretch()
        w.setWidget(inner)
        return w

    # ── Tab: Display ──
    def _tab_display(self) -> QWidget:
        w = QScrollArea()
        w.setWidgetResizable(True)
        w.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(20, 20, 20, 20)

        box, form = _form_group("Risoluzione e Colori")
        from core.models import RDPResolution, RDPColors
        resolutions = [r.value for r in RDPResolution]
        colors      = [c.value for c in RDPColors]
        self.f_resolution  = _combo(resolutions)
        self.f_auto_resize = _check("Ridimensionamento automatico")
        self.f_colors      = _combo(colors)
        self.f_cache_bitmaps   = _check("Cache bitmap")
        self.f_wallpaper       = _check("Mostra sfondo desktop")
        self.f_themes          = _check("Mostra temi desktop")
        self.f_font_smooth     = _check("Font smoothing")
        self.f_desktop_comp    = _check("Desktop composition")
        self.f_no_full_drag    = _check("Disabilita drag finestre")
        self.f_no_menu_anim    = _check("Disabilita animazioni menu")
        form.addRow(_label("Risoluzione:"),   self.f_resolution)
        form.addRow("", self.f_auto_resize)
        form.addRow(_label("Colori:"),        self.f_colors)
        form.addRow("", self.f_cache_bitmaps)
        form.addRow("", self.f_wallpaper)
        form.addRow("", self.f_themes)
        form.addRow("", self.f_font_smooth)
        form.addRow("", self.f_desktop_comp)
        form.addRow("", self.f_no_full_drag)
        form.addRow("", self.f_no_menu_anim)
        layout.addWidget(box)
        layout.addStretch()
        w.setWidget(inner)
        return w

    # ── Tab: Redirect ──
    def _tab_redirect(self) -> QWidget:
        w = QScrollArea()
        w.setWidgetResizable(True)
        w.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(20, 20, 20, 20)

        box, form = _form_group("Reindirizzamento")
        from core.models import RDPSound
        sound_opts = [s.value for s in RDPSound]
        self.f_redirect_drives     = _check("Disco fisso")
        self.f_redirect_printers   = _check("Stampanti")
        self.f_redirect_clipboard  = _check("Appunti")
        self.f_redirect_ports      = _check("Porte seriali")
        self.f_redirect_smartcards = _check("Smart Card")
        self.f_redirect_keys       = _check("Tasti speciali")
        self.f_redirect_audio_cap  = _check("Cattura audio")
        self.f_redirect_sound      = _combo(sound_opts)
        form.addRow("", self.f_redirect_drives)
        form.addRow("", self.f_redirect_printers)
        form.addRow("", self.f_redirect_clipboard)
        form.addRow("", self.f_redirect_ports)
        form.addRow("", self.f_redirect_smartcards)
        form.addRow("", self.f_redirect_keys)
        form.addRow("", self.f_redirect_audio_cap)
        form.addRow(_label("Audio:"), self.f_redirect_sound)
        layout.addWidget(box)
        layout.addStretch()
        w.setWidget(inner)
        return w

    # ── Tab: VNC ──
    def _tab_vnc(self) -> QWidget:
        w = QScrollArea()
        w.setWidgetResizable(True)
        w.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(20, 20, 20, 20)

        box, form = _form_group("VNC")
        from core.models import VNCCompression, VNCEncoding, VNCAuthMode, VNCProxyType
        self.f_vnc_comp    = _combo([c.value for c in VNCCompression])
        self.f_vnc_enc     = _combo([e.value for e in VNCEncoding])
        self.f_vnc_auth    = _combo([a.value for a in VNCAuthMode])
        self.f_vnc_viewonly = _check("Solo visualizzazione")
        form.addRow(_label("Compressione:"), self.f_vnc_comp)
        form.addRow(_label("Encoding:"),     self.f_vnc_enc)
        form.addRow(_label("Auth:"),         self.f_vnc_auth)
        form.addRow("", self.f_vnc_viewonly)
        layout.addWidget(box)

        box2, form2 = _form_group("Proxy VNC")
        self.f_vnc_proxy_type = _combo([p.value for p in VNCProxyType])
        self.f_vnc_proxy_ip   = _line_edit()
        self.f_vnc_proxy_port = QSpinBox()
        self.f_vnc_proxy_port.setRange(0, 65535)
        self.f_vnc_proxy_port.setStyleSheet(f"background: #1E1E1E; color: {TEXT_COLOR}; border: 1px solid #333; border-radius: 3px;")
        self.f_vnc_proxy_user = _line_edit()
        self.f_vnc_proxy_pass = _password_edit()
        form2.addRow(_label("Tipo proxy:"), self.f_vnc_proxy_type)
        form2.addRow(_label("IP proxy:"),   self.f_vnc_proxy_ip)
        form2.addRow(_label("Porta proxy:"), self.f_vnc_proxy_port)
        form2.addRow(_label("Utente:"),     self.f_vnc_proxy_user)
        form2.addRow(_label("Password:"),   self.f_vnc_proxy_pass)
        layout.addWidget(box2)
        layout.addStretch()
        w.setWidget(inner)
        return w

    # ── Tab: Altro ──
    def _tab_misc(self) -> QWidget:
        w = QScrollArea()
        w.setWidgetResizable(True)
        w.setFrameShape(QFrame.Shape.NoFrame)
        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(20, 20, 20, 20)

        box, form = _form_group("Strumenti esterni")
        self.f_pre_ext  = _line_edit()
        self.f_post_ext = _line_edit()
        self.f_ext_app  = _line_edit()
        form.addRow(_label("Pre-connessione:"),  self.f_pre_ext)
        form.addRow(_label("Post-connessione:"), self.f_post_ext)
        form.addRow(_label("Ext App:"),          self.f_ext_app)
        layout.addWidget(box)

        box2, form2 = _form_group("Rete")
        self.f_mac_address = _line_edit()
        self.f_user_field  = _line_edit()
        self.f_tags        = _line_edit()
        self.f_favorite    = _check("Connessione preferita ⭐")
        form2.addRow(_label("MAC Address:"), self.f_mac_address)
        form2.addRow(_label("Campo utente:"), self.f_user_field)
        form2.addRow(_label("Tag:"),          self.f_tags)
        form2.addRow("", self.f_favorite)
        layout.addWidget(box2)

        layout.addStretch()
        w.setWidget(inner)
        return w

    # ── Carica e salva dati ──
    def _load_data(self):
        c = self.conn
        self.f_name.setText(c.name)
        self.f_desc.setText(c.description)
        self.f_hostname.setText(c.hostname)
        self.f_port.setValue(c.port)
        self.f_protocol.setCurrentText(c.protocol.value)
        self.f_panel.setText(c.panel)

        self.f_username.setText(c.username)
        from core.crypto import decrypt
        self.f_password.setText(decrypt(c.password) if c.password else "")
        self.f_domain.setText(c.domain)
        self.f_putty_session.setText(c.putty_session)
        self.f_ssh_options.setText(c.ssh_options)
        self.f_opening_cmd.setText(c.opening_command)
        self.f_ssh_tunnel.setText(c.ssh_tunnel_name)

        self.f_rdp_version.setCurrentText(c.rdp_version)
        self.f_rdp_auth.setCurrentText(c.rdp_auth_level.value)
        self.f_use_console.setChecked(c.use_console_session)
        self.f_use_cred_ssp.setChecked(c.use_cred_ssp)
        self.f_restricted_admin.setChecked(c.use_restricted_admin)
        self.f_idle_timeout.setValue(c.rdp_idle_timeout)
        self.f_alert_idle.setChecked(c.rdp_alert_idle)
        self.f_load_balance.setText(c.load_balance_info)
        self.f_start_program.setText(c.rdp_start_program)
        self.f_start_workdir.setText(c.rdp_start_program_workdir)

        self.f_rdg_usage.setCurrentText(c.rdg_usage.value)
        self.f_rdg_hostname.setText(c.rdg_hostname)
        self.f_rdg_username.setText(c.rdg_username)
        self.f_rdg_password.setText(decrypt(c.rdg_password) if c.rdg_password else "")
        self.f_rdg_domain.setText(c.rdg_domain)

        self.f_resolution.setCurrentText(c.resolution.value)
        self.f_auto_resize.setChecked(c.automatic_resize)
        self.f_colors.setCurrentText(c.colors.value)
        self.f_cache_bitmaps.setChecked(c.cache_bitmaps)
        self.f_wallpaper.setChecked(c.display_wallpaper)
        self.f_themes.setChecked(c.display_themes)
        self.f_font_smooth.setChecked(c.font_smoothing)
        self.f_desktop_comp.setChecked(c.desktop_composition)
        self.f_no_full_drag.setChecked(c.disable_full_window_drag)
        self.f_no_menu_anim.setChecked(c.disable_menu_animations)

        self.f_redirect_drives.setChecked(c.redirect_drives == "All")
        self.f_redirect_printers.setChecked(c.redirect_printers)
        self.f_redirect_clipboard.setChecked(c.redirect_clipboard)
        self.f_redirect_ports.setChecked(c.redirect_ports)
        self.f_redirect_smartcards.setChecked(c.redirect_smart_cards)
        self.f_redirect_keys.setChecked(c.redirect_keys)
        self.f_redirect_audio_cap.setChecked(c.redirect_audio_capture)
        self.f_redirect_sound.setCurrentText(c.redirect_sound.value)

        self.f_vnc_comp.setCurrentText(c.vnc_compression.value)
        self.f_vnc_enc.setCurrentText(c.vnc_encoding.value)
        self.f_vnc_auth.setCurrentText(c.vnc_auth_mode.value)
        self.f_vnc_viewonly.setChecked(c.vnc_view_only)
        self.f_vnc_proxy_type.setCurrentText(c.vnc_proxy_type.value)
        self.f_vnc_proxy_ip.setText(c.vnc_proxy_ip)
        self.f_vnc_proxy_port.setValue(c.vnc_proxy_port)
        self.f_vnc_proxy_user.setText(c.vnc_proxy_user)
        self.f_vnc_proxy_pass.setText(decrypt(c.vnc_proxy_pass) if c.vnc_proxy_pass else "")

        self.f_pre_ext.setText(c.pre_ext_app)
        self.f_post_ext.setText(c.post_ext_app)
        self.f_ext_app.setText(c.ext_app)
        self.f_mac_address.setText(c.mac_address)
        self.f_user_field.setText(c.user_field)
        self.f_tags.setText(c.tags)
        self.f_favorite.setChecked(c.favorite)

    def _on_protocol_changed(self, proto: str):
        from core.models import ProtocolType
        try:
            pt = ProtocolType(proto)
            port = self.conn.get_default_port() if proto == self.conn.protocol.value else _default_port(pt)
            if port:
                self.f_port.setValue(port)
        except ValueError:
            pass
        self._update_tab_visibility(proto)

    def _update_tab_visibility(self, proto: str):
        """Mostra/nasconde le tab in base al protocollo selezionato."""
        # Tab indices: 0=Protocollo, 1=Credenziali, 2=RDP, 3=RD Gateway,
        #              4=Schermo, 5=Redirect, 6=VNC, 7=Altro
        rdp_only  = {2, 3, 4, 5}   # tab solo per RDP
        vnc_only  = {6}             # tab solo per VNC/ARD
        is_rdp    = proto == "RDP"
        is_vnc    = proto in ("VNC", "ARD")
        for i in rdp_only:
            self.tabs.setTabVisible(i, is_rdp)
        for i in vnc_only:
            self.tabs.setTabVisible(i, is_vnc)
        # Se la tab selezionata è ora nascosta, torna alla prima visibile
        cur = self.tabs.currentIndex()
        if not self.tabs.isTabVisible(cur):
            for i in range(self.tabs.count()):
                if self.tabs.isTabVisible(i):
                    self.tabs.setCurrentIndex(i)
                    break

    def _on_accept(self):
        c = self.conn
        c.name        = self.f_name.text().strip() or "Nuova Connessione"
        c.description = self.f_desc.text()
        import re
        raw_host = self.f_hostname.text().strip()
        c.hostname = re.sub(r'\.{2,}', '.', raw_host).rstrip('.')
        c.port        = self.f_port.value()
        from core.models import ProtocolType
        c.protocol    = ProtocolType(self.f_protocol.currentText())
        c.panel       = self.f_panel.text()

        c.username        = self.f_username.text()
        from core.crypto import encrypt
        pw = self.f_password.text()
        c.password        = encrypt(pw) if pw else ""
        c.domain          = self.f_domain.text()
        c.putty_session   = self.f_putty_session.text()
        c.ssh_options     = self.f_ssh_options.text()
        c.opening_command = self.f_opening_cmd.text()
        c.ssh_tunnel_name = self.f_ssh_tunnel.text()

        c.rdp_version          = self.f_rdp_version.currentText()
        from core.models import RDPAuthLevel
        c.rdp_auth_level       = RDPAuthLevel(self.f_rdp_auth.currentText())
        c.use_console_session  = self.f_use_console.isChecked()
        c.use_cred_ssp         = self.f_use_cred_ssp.isChecked()
        c.use_restricted_admin = self.f_restricted_admin.isChecked()
        c.rdp_idle_timeout     = self.f_idle_timeout.value()
        c.rdp_alert_idle       = self.f_alert_idle.isChecked()
        c.load_balance_info    = self.f_load_balance.text()
        c.rdp_start_program    = self.f_start_program.text()
        c.rdp_start_program_workdir = self.f_start_workdir.text()

        from core.models import RDGatewayUsage
        c.rdg_usage    = RDGatewayUsage(self.f_rdg_usage.currentText())
        c.rdg_hostname = self.f_rdg_hostname.text()
        c.rdg_username = self.f_rdg_username.text()
        rdg_pw = self.f_rdg_password.text()
        c.rdg_password = encrypt(rdg_pw) if rdg_pw else ""
        c.rdg_domain   = self.f_rdg_domain.text()

        from core.models import RDPResolution, RDPColors
        c.resolution       = RDPResolution(self.f_resolution.currentText())
        c.automatic_resize = self.f_auto_resize.isChecked()
        c.colors           = RDPColors(self.f_colors.currentText())
        c.cache_bitmaps    = self.f_cache_bitmaps.isChecked()
        c.display_wallpaper = self.f_wallpaper.isChecked()
        c.display_themes   = self.f_themes.isChecked()
        c.font_smoothing   = self.f_font_smooth.isChecked()
        c.desktop_composition = self.f_desktop_comp.isChecked()
        c.disable_full_window_drag = self.f_no_full_drag.isChecked()
        c.disable_menu_animations  = self.f_no_menu_anim.isChecked()

        c.redirect_drives  = "All" if self.f_redirect_drives.isChecked() else "None"
        c.redirect_printers = self.f_redirect_printers.isChecked()
        c.redirect_clipboard = self.f_redirect_clipboard.isChecked()
        c.redirect_ports   = self.f_redirect_ports.isChecked()
        c.redirect_smart_cards = self.f_redirect_smartcards.isChecked()
        c.redirect_keys    = self.f_redirect_keys.isChecked()
        c.redirect_audio_capture = self.f_redirect_audio_cap.isChecked()
        from core.models import RDPSound
        c.redirect_sound   = RDPSound(self.f_redirect_sound.currentText())

        from core.models import VNCCompression, VNCEncoding, VNCAuthMode, VNCProxyType
        c.vnc_compression  = VNCCompression(self.f_vnc_comp.currentText())
        c.vnc_encoding     = VNCEncoding(self.f_vnc_enc.currentText())
        c.vnc_auth_mode    = VNCAuthMode(self.f_vnc_auth.currentText())
        c.vnc_view_only    = self.f_vnc_viewonly.isChecked()
        c.vnc_proxy_type   = VNCProxyType(self.f_vnc_proxy_type.currentText())
        c.vnc_proxy_ip     = self.f_vnc_proxy_ip.text()
        c.vnc_proxy_port   = self.f_vnc_proxy_port.value()
        c.vnc_proxy_user   = self.f_vnc_proxy_user.text()
        vnc_pp = self.f_vnc_proxy_pass.text()
        c.vnc_proxy_pass   = encrypt(vnc_pp) if vnc_pp else ""

        c.pre_ext_app  = self.f_pre_ext.text()
        c.post_ext_app = self.f_post_ext.text()
        c.ext_app      = self.f_ext_app.text()
        c.mac_address  = self.f_mac_address.text()
        c.user_field   = self.f_user_field.text()
        c.tags         = self.f_tags.text()
        c.favorite     = self.f_favorite.isChecked()

        self.accept()


def _default_port(protocol) -> int:
    from core.models import ProtocolType
    mapping = {
        ProtocolType.RDP: 3389, ProtocolType.VNC: 5900, ProtocolType.ARD: 5900,
        ProtocolType.SSH2: 22, ProtocolType.Telnet: 23,
        ProtocolType.Rlogin: 513, ProtocolType.RAW: 23,
        ProtocolType.HTTP: 80, ProtocolType.HTTPS: 443, ProtocolType.PowerShell: 5985,
    }
    return mapping.get(protocol, 0)
