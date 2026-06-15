"""
Finestra principale - layout identico a MobaXterm (dark theme).
"""
from __future__ import annotations
import math
import os
import re
import sys
from typing import Dict, Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTabWidget, QTabBar, QToolBar, QStatusBar, QLabel, QLineEdit,
    QPushButton, QComboBox, QMessageBox, QFrame, QSizePolicy,
    QStackedWidget, QApplication, QStyle
)
from PyQt6.QtCore import Qt, QSize, QPointF, QRectF, pyqtSignal, QTimer
from PyQt6.QtGui import (
    QAction, QFont, QKeySequence, QColor, QPainter, QPainterPath, QPen,
    QPixmap, QIcon, QLinearGradient
)

from themes.dark_theme import DARK_QSS, ACCENT_COLOR, CARD_COLOR, TEXT_COLOR, SUB_COLOR, BG_COLOR
from ui.connection_tree import ConnectionTreePanel
from ui.home_panel import HomePanel
from ui.dashboard_panel import DashboardPanel
from ui.toast import ToastManager
from core.models import ConnectionInfo, ContainerInfo, RootNode
from config.xml_parser import load_connections, save_connections

# Percorso config: usa prima shared/ (struttura unificata), poi fallback APPDATA
_THIS_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SHARED_XML = os.path.join(_THIS_DIR, "..", "shared", "confCons.xml")
_SHARED_XML = os.path.normpath(_SHARED_XML)

DEFAULT_CONNS_PATH = (
    _SHARED_XML if os.path.isdir(os.path.dirname(_SHARED_XML))
    else os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                      "Nexus", "confCons.xml")
)

# ─────────────────────────────────────────────────────────────
# Tab connessione aperta
# ─────────────────────────────────────────────────────────────
class ConnectionTab(QWidget):
    def __init__(self, conn: ConnectionInfo, parent=None):
        super().__init__(parent)
        self.conn      = conn
        self._protocol = None
        QVBoxLayout(self).setContentsMargins(0, 0, 0, 0)

    def connect(self):
        from protocols.factory import create_protocol
        self._protocol = create_protocol(self.conn, self)
        self.layout().addWidget(self._protocol.get_widget())
        return self._protocol.connect()

    def disconnect(self):
        if self._protocol:
            self._protocol.disconnect()

    def send_keys(self, keys: str):
        if self._protocol:
            self._protocol.send_special_keys(keys)


# ─────────────────────────────────────────────────────────────
# Pannello tab laterale verticale (stile MobaXterm)
# ─────────────────────────────────────────────────────────────
class _TabButton(QWidget):
    """Singolo bottone della sidebar: icona grande + etichetta proporzionata."""
    clicked = pyqtSignal()

    def __init__(self, icon: str, name: str, color: str, tip: str,
                 checked: bool = False):
        super().__init__()
        self._color  = color
        self._checked = False
        self.setObjectName("tabBtn")
        self.setFixedSize(80, 82)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f"<b>{name}</b><br>{tip}")

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 14, 0, 10)
        lay.setSpacing(7)

        self._icon_lbl = QLabel(icon)
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._icon_lbl)

        self._name_lbl = QLabel(name)
        self._name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._name_lbl)

        self._apply_state(checked)

    def _apply_state(self, checked: bool):
        self._checked = checked
        if checked:
            self.setStyleSheet(
                f"QWidget#tabBtn {{ background:#0D1A0D;"
                f" border-left:3px solid {self._color}; }}"
            )
            self._icon_lbl.setStyleSheet(
                f"font-size:24px; color:{self._color}; background:transparent;"
            )
            self._name_lbl.setStyleSheet(
                f"font-size:11px; font-weight:bold; color:{self._color};"
                " background:transparent;"
            )
        else:
            self.setStyleSheet(
                "QWidget#tabBtn { background:transparent;"
                " border-left:3px solid transparent; }"
            )
            self._icon_lbl.setStyleSheet(
                "font-size:24px; color:#4A4A4A; background:transparent;"
            )
            self._name_lbl.setStyleSheet(
                "font-size:11px; color:#4A4A4A; background:transparent;"
            )

    def setChecked(self, v: bool):
        self._apply_state(v)

    def isChecked(self) -> bool:
        return self._checked

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(e)

    def enterEvent(self, e):
        if not self._checked:
            self.setStyleSheet(
                "QWidget#tabBtn { background:#1A1A1A;"
                " border-left:3px solid #2A2A2A; }"
            )
            self._icon_lbl.setStyleSheet(
                "font-size:24px; color:#888888; background:transparent;"
            )
            self._name_lbl.setStyleSheet(
                "font-size:11px; color:#888888; background:transparent;"
            )
        super().enterEvent(e)

    def leaveEvent(self, e):
        if not self._checked:
            self._apply_state(False)
        super().leaveEvent(e)


class VerticalTabBar(QWidget):
    """Barra tab verticale stile MobaXterm."""
    tab_changed = pyqtSignal(int)

    TABS = [
        ("Sessions",  "🖥",  "#4EC94E",
         "Gestione connessioni salvate (SSH, RDP, VNC…)"),
        ("Bookmarks", "🔖",  "#FFC107",
         "Segnalibri: connessioni preferite ad accesso rapido"),
        ("Tools",     "🔧",  "#5BA8E5",
         "Port Scanner, Ping Monitor, Network Discovery"),
        ("Macros",    "⚡",  "#F5A623",
         "Macro: comandi automatici da inviare alle sessioni"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(80)
        self.setStyleSheet("background:#111111; border-right:1px solid #1A1A1A;")
        self._current = 0
        self._btns: list[_TabButton] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 6, 0, 6)
        layout.setSpacing(2)

        for i, (name, icon, color, tip) in enumerate(self.TABS):
            btn = _TabButton(icon, name, color, tip, checked=(i == 0))
            idx = i
            btn.clicked.connect(lambda x=idx: self._on_click(x))
            layout.addWidget(btn)
            self._btns.append(btn)

        layout.addStretch()

    def _on_click(self, idx: int):
        self._current = idx
        for i, b in enumerate(self._btns):
            b.setChecked(i == idx)
        self.tab_changed.emit(idx)


# ─────────────────────────────────────────────────────────────
# TabBar con X rossa sempre visibile
# ─────────────────────────────────────────────────────────────
class _CloseTabBar(QTabBar):
    """QTabBar che aggiunge un pulsante X rosso su ogni tab."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDrawBase(False)
        self.setExpanding(False)
        self.setMovable(True)
        self.setStyleSheet(f"""
            QTabBar {{
                background: #141414;
                border-bottom: 1px solid #2A2A2A;
            }}
            QTabBar::tab {{
                background: #141414;
                color: {SUB_COLOR};
                border: none;
                border-right: 1px solid #222;
                padding: 0 34px 0 14px;
                min-height: 40px;
                min-width: 160px;
                max-width: 300px;
                font-size: 12px;
            }}
            QTabBar::tab:selected {{
                background: {BG_COLOR};
                color: {TEXT_COLOR};
                border-top: 2px solid {ACCENT_COLOR};
            }}
            QTabBar::tab:hover:!selected {{
                background: #1A1A1A;
                color: {TEXT_COLOR};
            }}
            QTabBar::close-button {{
                subcontrol-position: right;
                subcontrol-origin: padding;
                image: none;
                width: 16px;
                height: 16px;
                margin-right: 4px;
            }}
        """)

    def tabSizeHint(self, index: int) -> QSize:
        s = super().tabSizeHint(index)
        return QSize(max(s.width(), 165), 40)

    def _setup_close_buttons(self):
        """Sostituisce i close button con widget QPushButton rossi."""
        for i in range(self.count()):
            existing = self.tabButton(i, QTabBar.ButtonPosition.RightSide)
            if existing:
                continue
            btn = QPushButton("✕")
            btn.setFixedSize(18, 18)
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: #555;
                    border: none;
                    border-radius: 9px;
                    font-size: 11px;
                    font-weight: bold;
                    padding: 0;
                }
                QPushButton:hover  { background: #EF5350; color: white; }
                QPushButton:pressed{ background: #B71C1C; color: white; }
            """)
            tab_idx = i
            btn.clicked.connect(lambda _, x=tab_idx: self._btn_clicked(x))
            self.setTabButton(i, QTabBar.ButtonPosition.RightSide, btn)

    def _btn_clicked(self, static_idx: int):
        # Trova il tab tramite il pulsante che ha emesso il segnale
        btn = self.sender()
        for i in range(self.count()):
            w = self.tabButton(i, QTabBar.ButtonPosition.RightSide)
            if w is btn:
                self.tabCloseRequested.emit(i)
                return


# ─────────────────────────────────────────────────────────────
# Barra sessioni attive (sopra i tab)
# ─────────────────────────────────────────────────────────────
class _ActiveSessionsBar(QWidget):
    """
    Barra compatta sopra i tab: mostra le sessioni attive come pill colorati
    con un X per chiuderle. Nascosta quando non ci sono sessioni.
    """
    close_requested = pyqtSignal(str)   # conn_id

    _PROTO_COLORS = {
        "SSH2": "#4EC94E", "RDP": "#4E9EEC",
        "VNC": "#EC8C4E", "HTTP": "#A78FEC", "HTTPS": "#A78FEC",
        "Telnet": "#E0C44E",
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(0)   # nascosta di default
        self.setStyleSheet(
            "background:#0A0A0A; border-bottom:1px solid #1A1A1A;"
        )
        outer = QHBoxLayout(self)
        outer.setContentsMargins(8, 4, 8, 4)
        outer.setSpacing(0)

        lbl = QLabel("Sessioni attive:")
        lbl.setStyleSheet(f"color:{SUB_COLOR}; font-size:10px; font-weight:bold; background:transparent;")
        lbl.setContentsMargins(0, 0, 6, 0)
        outer.addWidget(lbl)

        self._chips_widget = QWidget()
        self._chips_widget.setStyleSheet("background:transparent;")
        self._chips_layout = QHBoxLayout(self._chips_widget)
        self._chips_layout.setContentsMargins(0, 0, 0, 0)
        self._chips_layout.setSpacing(4)
        self._chips_layout.addStretch()
        outer.addWidget(self._chips_widget)
        self._chips: list = []

    def refresh(self, open_tabs: dict):
        for chip in self._chips:
            self._chips_layout.removeWidget(chip)
            chip.deleteLater()
        self._chips.clear()

        if not open_tabs:
            self.setFixedHeight(0)
            return

        self.setFixedHeight(40)
        for conn_id, tab in open_tabs.items():
            conn  = tab.conn
            proto = conn.protocol.value if hasattr(conn.protocol, "value") else str(conn.protocol)
            color = self._PROTO_COLORS.get(proto, "#888888")
            chip  = self._make_chip(conn.name, proto, color, conn_id)
            self._chips_layout.insertWidget(self._chips_layout.count() - 1, chip)
            self._chips.append(chip)

    def _make_chip(self, name: str, proto: str, color: str, conn_id: str) -> QWidget:
        chip = QWidget()
        chip.setFixedHeight(26)
        chip.setStyleSheet(
            f"QWidget {{ background:#141414; border:1px solid {color}55;"
            f" border-radius:13px; }}"
        )
        lay = QHBoxLayout(chip)
        lay.setContentsMargins(9, 0, 6, 0)
        lay.setSpacing(5)

        dot = QLabel("●")
        dot.setStyleSheet(f"color:{color}; font-size:8px; background:transparent; border:none;")
        dot.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        lay.addWidget(dot)

        proto_lbl = QLabel(proto)
        proto_lbl.setStyleSheet(
            f"color:{color}; font-size:9px; font-weight:bold; background:transparent; border:none;"
        )
        proto_lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Preferred)
        lay.addWidget(proto_lbl)

        name_short = name[:18] + "…" if len(name) > 18 else name
        name_lbl = QLabel(name_short)
        name_lbl.setStyleSheet("color:#CCCCCC; font-size:11px; background:transparent; border:none;")
        name_lbl.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        lay.addWidget(name_lbl)

        btn = QPushButton("✕")
        btn.setFixedSize(16, 16)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            "QPushButton { background:transparent; color:#555; border:none;"
            " border-radius:8px; font-size:9px; font-weight:bold; }"
            "QPushButton:hover { background:#EF5350; color:white; }"
        )
        cid = conn_id
        btn.clicked.connect(lambda: self.close_requested.emit(cid))
        lay.addWidget(btn)

        # Width determined naturally by content — no setFixedWidth
        return chip


# ─────────────────────────────────────────────────────────────
# Finestra principale
# ─────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self._root: RootNode   = RootNode()
        self._open_tabs: Dict[str, ConnectionTab] = {}
        self._conns_path = DEFAULT_CONNS_PATH

        self.setWindowTitle("Nexus")
        self.setMinimumSize(1100, 680)
        self.resize(1420, 860)
        self.setStyleSheet(DARK_QSS)

        from ui.icon_generator import create_app_icon
        self.setWindowIcon(create_app_icon(64))

        self._setup_menu()
        self._setup_toolbar()
        self._setup_quickconnect_bar()
        self._setup_central()
        self._setup_statusbar()
        self._load_connections()
        self._start_scheduler()

        # Inizializza toast dopo che la finestra è costruita
        ToastManager.init(self)

    # ──────────────────────────────────────────
    # MENU BAR  (stile MobaXterm)
    # ──────────────────────────────────────────
    def _setup_menu(self):
        mb = self.menuBar()
        mb.setStyleSheet(f"""
            QMenuBar {{
                background-color: #141414;
                color: {TEXT_COLOR};
                border-bottom: 1px solid #2A2A2A;
                font-size: 12px;
                padding: 2px 0;
            }}
            QMenuBar::item {{ padding: 4px 10px; }}
            QMenuBar::item:selected {{ background: #2A2A2A; }}
            QMenuBar::item:pressed  {{ background: {ACCENT_COLOR}; color: white; }}
            QMenu {{
                background: #1A1A1A; color: {TEXT_COLOR};
                border: 1px solid #333;
            }}
            QMenu::item:selected {{ background: {ACCENT_COLOR}; color: white; }}
            QMenu::separator {{ background: #333; height: 1px; margin: 3px 8px; }}
        """)

        def menu(title):
            return mb.addMenu(title)

        # Terminal
        m = menu("Terminal")
        m.addAction("Nuova sessione\tCtrl+N",
                    lambda: self._on_new_connection(None)).setShortcut("Ctrl+N")
        m.addAction("Duplica sessione\tCtrl+D",
                    self._on_duplicate_session).setShortcut("Ctrl+D")
        m.addSeparator()
        m.addAction("Chiudi sessione\tCtrl+W",
                    self._disconnect_current).setShortcut("Ctrl+W")
        m.addSeparator()
        m.addAction("Esci\tAlt+F4", self.close)

        # Sessions
        m2 = menu("Sessions")
        m2.addAction("Salva sessioni\tCtrl+S",
                     self._save_connections).setShortcut("Ctrl+S")
        m2.addAction("Importa sessioni XML...", self._open_file)
        m2.addAction("Importa da MobaXterm...", self._on_import_mobaxterm)
        m2.addSeparator()
        m2.addAction("Chiudi tutte le sessioni", self._close_all_connections)

        # View
        m3 = menu("View")
        m3.addAction("Home", self._show_home)
        m3.addAction("Pannello sessioni", lambda: self._left_stack.setCurrentIndex(0))

        # Tools
        m4 = menu("Tools")
        m4.addAction("Port Scanner / Ping Monitor", self._on_show_tools)
        m4.addAction("Network Discovery...", self._on_network_discovery)
        m4.addSeparator()
        m4.addAction("Script Scheduler...", self._on_scheduler)
        m4.addSeparator()
        m4.addAction("Impostazioni", self._show_settings)

        # Admin
        m5 = menu("Admin")
        m5.addAction("Gestione Utenti...", self._on_user_manager)
        m5.addSeparator()
        m5.addAction("Log Sessioni...", self._on_session_logs)
        m5.addAction("Esporta Report...", self._on_report)

        # Settings
        m6 = menu("Settings")
        m6.addAction("Configurazione...", self._show_settings)

        # Help
        m7 = menu("Help")
        m7.addAction("Informazioni", self._show_about)

    # ──────────────────────────────────────────
    # TOOLBAR ICONE GRANDI  (stile MobaXterm)
    # ──────────────────────────────────────────
    def _setup_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setIconSize(QSize(40, 40))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        tb.setStyleSheet(f"""
            QToolBar {{
                background-color: #161616;
                border: none;
                border-bottom: 1px solid #1A1A1A;
                spacing: 0px;
                padding: 3px 4px;
            }}
            QToolButton {{
                background: transparent;
                color: {TEXT_COLOR};
                border: none;
                border-radius: 4px;
                padding: 4px 6px 2px 6px;
                font-size: 11px;
                min-width: 52px;
            }}
            QToolButton:hover  {{ background: #222222; }}
            QToolButton:pressed {{ background: {ACCENT_COLOR}; color: white; }}
            QToolBar::separator {{
                background: #252525;
                width: 1px;
                margin: 6px 2px;
            }}
        """)

        def _make_icon(name: str, size: int = 40) -> QIcon:
            configs = {
                "session":   ("#1B3A1E", "#4EC94E"),
                "sessions":  ("#162233", "#5BA8E5"),
                "split":     ("#1E1530", "#9B7FE8"),
                "multiexec": ("#2E2000", "#F5A623"),
                "tunneling": ("#141430", "#5BA8E5"),
                "tools":     ("#261A1A", "#B8B8B8"),
                "settings":  ("#1C1C1C", "#A0A0A0"),
                "save":      ("#163020", "#26C9A8"),
                "open":      ("#2A2510", "#FFC107"),
                "xserver":   ("#1A1428", "#8B80D8"),
                "exit":      ("#361010", "#EF5350"),
            }
            bg_hex, fg_hex = configs.get(name, ("#1A1A1A", "#AAAAAA"))
            bg = QColor(bg_hex)
            fg = QColor(fg_hex)

            px = QPixmap(size, size)
            px.fill(Qt.GlobalColor.transparent)
            p = QPainter(px)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)

            # Rounded background
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(bg)
            p.drawRoundedRect(0, 0, size, size, 7, 7)

            m = size * 0.18
            w = size - 2 * m

            if name == "session":
                thick = size * 0.13
                p.setBrush(fg)
                p.setPen(Qt.PenStyle.NoPen)
                p.drawRoundedRect(int(m), int(size/2 - thick/2), int(w), int(thick),
                                  int(thick/2), int(thick/2))
                p.drawRoundedRect(int(size/2 - thick/2), int(m), int(thick), int(w),
                                  int(thick/2), int(thick/2))

            elif name == "sessions":
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(fg)
                fy = size * 0.30
                fh = size * 0.44
                p.drawRoundedRect(int(m), int(fy), int(w), int(fh), 3, 3)
                p.drawRoundedRect(int(m), int(fy - size*0.10), int(w*0.42), int(size*0.13), 2, 2)
                p.setBrush(bg)
                for i in range(3):
                    ly = fy + fh * 0.22 + i * fh * 0.25
                    p.drawRoundedRect(int(m + size*0.06), int(ly), int(w*0.72), int(size*0.05), 1, 1)

            elif name == "split":
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(fg)
                gap = size * 0.07
                cw = (w - gap) / 2
                ch = (w - gap) / 2
                for row in range(2):
                    for col in range(2):
                        x = m + col * (cw + gap)
                        y = m + row * (ch + gap)
                        p.drawRoundedRect(int(x), int(y), int(cw), int(ch), 2, 2)

            elif name == "multiexec":
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(fg)
                cx = size / 2
                path = QPainterPath()
                pts = [
                    QPointF(cx + size*0.08, m),
                    QPointF(cx - size*0.05, size*0.47),
                    QPointF(cx + size*0.10, size*0.47),
                    QPointF(cx - size*0.08, size - m),
                    QPointF(cx + size*0.05, size*0.53),
                    QPointF(cx - size*0.10, size*0.53),
                ]
                path.moveTo(pts[0])
                for pt in pts[1:]:
                    path.lineTo(pt)
                path.closeSubpath()
                p.drawPath(path)

            elif name == "tunneling":
                pen = QPen(fg, size * 0.085)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                # Top-left link
                p.drawEllipse(QRectF(m - size*0.04, m + size*0.08, w*0.55, w*0.42))
                # Bottom-right link
                p.drawEllipse(QRectF(m + size*0.20, m + size*0.30, w*0.55, w*0.42))

            elif name == "tools":
                pen = QPen(fg, size * 0.09)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawLine(QPointF(m + w*0.58, m + w*0.02), QPointF(m + w*0.02, m + w*0.58))
                p.drawEllipse(QRectF(m, m + w*0.50, w*0.36, w*0.36))
                p.drawEllipse(QRectF(m + w*0.50, m, w*0.36, w*0.36))

            elif name == "settings":
                center = size / 2
                outer_r = w * 0.35
                inner_r = w * 0.18
                mid_r   = w * 0.28
                # Gear teeth
                p.setBrush(fg)
                p.setPen(Qt.PenStyle.NoPen)
                tw = size * 0.10
                th = size * 0.11
                for i in range(8):
                    angle = i * 2 * math.pi / 8
                    tx = center + outer_r * math.cos(angle)
                    ty = center + outer_r * math.sin(angle)
                    p.save()
                    p.translate(tx, ty)
                    p.rotate(math.degrees(angle))
                    p.drawRoundedRect(int(-tw/2), int(-th/2), int(tw), int(th), 1, 1)
                    p.restore()
                # Solid ring
                p.drawEllipse(QRectF(center - mid_r, center - mid_r, mid_r*2, mid_r*2))
                # Center hole
                p.setBrush(bg)
                p.drawEllipse(QRectF(center - inner_r, center - inner_r, inner_r*2, inner_r*2))

            elif name == "save":
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(fg)
                p.drawRoundedRect(int(m), int(m), int(w), int(w), 3, 3)
                # Notch top-right
                p.setBrush(bg)
                ns = w * 0.22
                p.drawRect(int(m + w - ns), int(m), int(ns), int(ns))
                # Label area
                label_y = m + w * 0.46
                p.setBrush(QColor(bg.red(), bg.green(), bg.blue(), 210))
                p.drawRoundedRect(int(m + w*0.08), int(label_y), int(w*0.84), int(w - (label_y-m)), 1, 1)
                # Metal shutter
                p.setBrush(fg.darker(140))
                p.drawRect(int(m + w*0.56), int(m + 1), int(w*0.25), int(w*0.32))
                p.setBrush(bg)
                p.drawRoundedRect(int(m + w*0.59), int(m + w*0.06), int(w*0.19), int(w*0.23), 1, 1)

            elif name == "open":
                p.setPen(Qt.PenStyle.NoPen)
                # Back folder
                p.setBrush(fg.darker(160))
                p.drawRoundedRect(int(m), int(size*0.30), int(w), int(size*0.44), 3, 3)
                # Tab
                p.drawRoundedRect(int(m), int(size*0.20), int(w*0.42), int(size*0.13), 2, 2)
                # Open flap (trapezoid)
                p.setBrush(fg)
                path = QPainterPath()
                path.moveTo(m,         size*0.40)
                path.lineTo(m + w,     size*0.40)
                path.lineTo(m + w - size*0.07, size*0.74)
                path.lineTo(m + size*0.07,     size*0.74)
                path.closeSubpath()
                p.drawPath(path)

            elif name == "xserver":
                pen = QPen(fg, size * 0.07)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                mw = w * 0.90
                mh = w * 0.58
                mx = m + (w - mw) / 2
                my = m + size * 0.02
                p.drawRoundedRect(int(mx), int(my), int(mw), int(mh), 2, 2)
                inn = size * 0.09
                p.drawLine(QPointF(mx + inn, my + inn),         QPointF(mx + mw - inn, my + mh - inn))
                p.drawLine(QPointF(mx + mw - inn, my + inn),    QPointF(mx + inn,      my + mh - inn))
                mid = size / 2
                bot = size - m - size * 0.02
                p.drawLine(QPointF(mid, my + mh),     QPointF(mid, bot - size*0.04))
                p.drawLine(QPointF(mid - w*0.20, bot), QPointF(mid + w*0.20, bot))

            elif name == "exit":
                pen = QPen(fg, size * 0.09)
                pen.setCapStyle(Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.setBrush(Qt.BrushStyle.NoBrush)
                center = size / 2
                r_c = w * 0.33
                gap = 52  # half-gap in degrees
                start = int((90 + gap) * 16)
                span  = int((360 - gap * 2) * 16)
                p.drawArc(QRectF(center - r_c, center - r_c, r_c*2, r_c*2), start, span)
                p.drawLine(QPointF(center, m), QPointF(center, center - r_c * 0.25))

            p.end()
            return QIcon(px)

        def btn(label: str, icon_name: str, cb, shortcut: str = ""):
            act = QAction(_make_icon(icon_name), label, self)
            if shortcut:
                act.setShortcut(shortcut)
            act.triggered.connect(cb)
            tb.addAction(act)
            return act

        btn("Session",   "session",   lambda: self._on_new_connection(None), "Ctrl+N")
        tb.addSeparator()
        btn("Dashboard", "sessions",  self._show_dashboard)
        btn("Split",     "split",     self._on_split)
        btn("MultiExec", "multiexec", self._on_multiexec)
        tb.addSeparator()
        btn("Tunneling", "tunneling", self._on_tunneling)
        btn("Tools",     "tools",     self._on_show_tools)
        btn("Settings",  "settings",  self._show_settings)
        tb.addSeparator()
        btn("Save",      "save",      self._save_connections, "Ctrl+S")
        btn("Open",      "open",      self._open_file)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        spacer.setStyleSheet("background: transparent;")
        tb.addWidget(spacer)

        btn("Exit",      "exit",      self.close)

        self.addToolBar(tb)

    # ──────────────────────────────────────────
    # QUICK CONNECT BAR  (riga sotto toolbar)
    # ──────────────────────────────────────────
    def _setup_quickconnect_bar(self):
        """Costruisce il widget Quick Connect. Viene aggiunto a _setup_central."""
        bar = QWidget()
        bar.setObjectName("quickconnect_bar")
        bar.setFixedHeight(34)
        bar.setStyleSheet(
            "background:#141414; border-bottom:1px solid #1A1A1A;"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(6)

        lbl = QLabel("Quick connect")
        lbl.setFixedWidth(90)
        lbl.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px; background:transparent;")
        layout.addWidget(lbl)

        self.quick_box = QLineEdit()
        self.quick_box.setPlaceholderText("utente@host  o  host:porta")
        self.quick_box.setFixedWidth(260)
        self.quick_box.setFixedHeight(24)
        self.quick_box.setStyleSheet(f"""
            QLineEdit {{
                background:#111111; color:{TEXT_COLOR};
                border:1px solid #252525; border-radius:4px;
                padding:2px 8px; font-size:12px;
            }}
            QLineEdit:focus {{ border-color:{ACCENT_COLOR}; }}
        """)
        self.quick_box.returnPressed.connect(self._on_quick_connect)
        layout.addWidget(self.quick_box)

        from core.models import ProtocolType
        self.proto_combo = QComboBox()
        for p in [ProtocolType.SSH2, ProtocolType.RDP, ProtocolType.VNC,
                  ProtocolType.Telnet, ProtocolType.HTTP, ProtocolType.HTTPS]:
            self.proto_combo.addItem(p.value)
        self.proto_combo.setFixedHeight(24)
        self.proto_combo.setFixedWidth(80)
        self.proto_combo.setStyleSheet(f"""
            QComboBox {{
                background:#111111; color:{TEXT_COLOR};
                border:1px solid #252525; border-radius:4px;
                padding:1px 6px; font-size:12px;
            }}
            QComboBox QAbstractItemView {{
                background:#111111; color:{TEXT_COLOR};
                selection-background-color:{ACCENT_COLOR};
            }}
            QComboBox::drop-down {{ border:none; width:16px; }}
        """)
        layout.addWidget(self.proto_combo)

        go_btn = QPushButton("Connetti")
        go_btn.setFixedHeight(24)
        go_btn.setStyleSheet(f"""
            QPushButton {{
                background:{ACCENT_COLOR}; color:white; border:none;
                border-radius:4px; padding:0 14px; font-size:12px; font-weight:bold;
            }}
            QPushButton:hover  {{ background:#0088DD; }}
            QPushButton:pressed {{ background:#005A9E; }}
        """)
        go_btn.clicked.connect(self._on_quick_connect)
        layout.addWidget(go_btn)
        layout.addStretch()

        self._qc_bar_widget = bar   # viene inserito in _setup_central

    # ──────────────────────────────────────────
    # WIDGET CENTRALE  (splitter MobaXterm)
    # ──────────────────────────────────────────
    def _setup_central(self):
        root = QWidget()
        root.setStyleSheet(f"background:{BG_COLOR};")
        root_lay = QVBoxLayout(root)
        root_lay.setContentsMargins(0, 0, 0, 0)
        root_lay.setSpacing(0)
        self.setCentralWidget(root)

        # ── Quick connect bar (allineata al layout, non più in QToolBar) ──
        root_lay.addWidget(self._qc_bar_widget)

        # ── Splitter: pannello sx | area centrale ──
        splitter_container = QWidget()
        splitter_container.setStyleSheet(f"background:{BG_COLOR};")
        h_layout = QHBoxLayout(splitter_container)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)
        root_lay.addWidget(splitter_container)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(1)
        self.splitter.setStyleSheet("QSplitter::handle { background: #1A1A1A; }")
        h_layout.addWidget(self.splitter)

        # ── Pannello sinistro: vtab + stack ──
        left_container = QWidget()
        left_container.setStyleSheet("background:#111111;")
        left_hlay = QHBoxLayout(left_container)
        left_hlay.setContentsMargins(0, 0, 0, 0)
        left_hlay.setSpacing(0)

        self.vtab = VerticalTabBar()
        self.vtab.tab_changed.connect(self._on_left_tab)
        left_hlay.addWidget(self.vtab)

        # Colonna destra del left container: header + stack
        left_right = QWidget()
        left_right.setStyleSheet("background:#111111;")
        left_right_lay = QVBoxLayout(left_right)
        left_right_lay.setContentsMargins(0, 0, 0, 0)
        left_right_lay.setSpacing(0)

        # Header contestuale — stessa altezza della quick connect bar (34px)
        self._left_header = QWidget()
        self._left_header.setFixedHeight(34)
        self._left_header.setStyleSheet(
            "background:#141414; border-bottom:1px solid #1A1A1A;"
        )
        lhh = QHBoxLayout(self._left_header)
        lhh.setContentsMargins(10, 0, 8, 0)
        lhh.setSpacing(6)
        self._left_header_icon = QLabel("🖥")
        self._left_header_icon.setStyleSheet(
            "background:transparent; font-size:13px; color:#4EC94E;"
        )
        self._left_header_name = QLabel("Sessions")
        self._left_header_name.setStyleSheet(
            f"background:transparent; color:#4EC94E; font-size:12px; font-weight:bold;"
        )
        self._left_header_desc = QLabel("Connessioni salvate")
        self._left_header_desc.setStyleSheet(
            f"background:transparent; color:{SUB_COLOR}; font-size:10px;"
        )
        lhh.addWidget(self._left_header_icon)
        lhh.addWidget(self._left_header_name)
        lhh.addWidget(self._left_header_desc)
        lhh.addStretch()
        left_right_lay.addWidget(self._left_header)

        self._left_stack = QStackedWidget()
        self._left_stack.setMinimumWidth(180)
        self._left_stack.setMaximumWidth(380)
        self._left_stack.setStyleSheet("background:#111111;")
        left_right_lay.addWidget(self._left_stack)

        left_hlay.addWidget(left_right)
        self.splitter.addWidget(left_container)

        # Pagina 0: Albero sessioni
        self.tree_panel = ConnectionTreePanel()
        self.tree_panel.connection_activated.connect(self._on_open_connection)
        self.tree_panel.connection_selected.connect(self._on_select_connection)
        self.tree_panel.new_connection_requested.connect(self._on_new_connection)
        self.tree_panel.new_folder_requested.connect(self._on_new_folder)
        self.tree_panel.delete_requested.connect(self._on_delete_connection)
        self.tree_panel.edit_requested.connect(self._on_edit_connection)
        self.tree_panel.rename_requested.connect(self._on_rename_connection)
        self.tree_panel.add_to_bookmarks.connect(self._on_add_to_bookmarks)
        self._left_stack.addWidget(self.tree_panel)

        # Pagina 1: Bookmarks (con sottocartelle)
        from ui.bookmarks_panel import BookmarksPanel
        self._bookmarks_panel = BookmarksPanel()
        self._bookmarks_panel.connection_activated.connect(self._on_open_connection)
        self._left_stack.addWidget(self._bookmarks_panel)

        # Pagina 2: Tools (port scanner, ping monitor, discovery)
        from ui.tools_panel import ToolsPanel
        self._tools_panel = ToolsPanel()
        self._tools_panel.hosts_discovered.connect(self._on_hosts_discovered)
        self._tools_panel.ping_monitor.host_down.connect(self._on_host_down)
        self._left_stack.addWidget(self._tools_panel)

        # Pagina 3: Macros
        from ui.macros_panel import MacrosPanel
        self._macros_panel = MacrosPanel()
        self._macros_panel.run_macro.connect(self._on_run_macro)
        self._left_stack.addWidget(self._macros_panel)

        # ── Area centrale: tab sessioni ──
        right = QWidget()
        right.setStyleSheet(f"background: {BG_COLOR};")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # ── Barra sessioni attive ──
        self._sessions_bar = _ActiveSessionsBar()
        self._sessions_bar.close_requested.connect(self._close_by_conn_id)
        right_layout.addWidget(self._sessions_bar)

        self._tab_bar = _CloseTabBar()
        self._tab_bar.tabCloseRequested.connect(self._on_tab_close)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabBar(self._tab_bar)
        self.tab_widget.setTabsClosable(False)
        self.tab_widget.setMovable(True)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setStyleSheet(
            f"QTabWidget::pane {{ background:{BG_COLOR}; border:none; }}"
        )

        # Widget di benvenuto (visibile quando nessuna sessione è aperta)
        self._welcome = QLabel(
            "← Seleziona una connessione nel pannello di sinistra\n"
            "oppure usa Quick Connect per avviare una nuova sessione"
        )
        self._welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._welcome.setWordWrap(True)
        self._welcome.setStyleSheet(
            f"color:{SUB_COLOR}; font-size:14px; background:{BG_COLOR}; padding:40px;"
        )
        right_layout.addWidget(self._welcome)
        right_layout.addWidget(self.tab_widget)
        self.splitter.addWidget(right)
        self.splitter.setSizes([240, 1000])

        # Dashboard come finestra separata (creata al primo click)
        self._dashboard: DashboardPanel | None = None
        self._dashboard_window: QWidget | None = None

        # home_panel mantenuto per compatibilità interna
        self.home_panel = HomePanel()
        self._update_welcome()

    # ──────────────────────────────────────────
    # STATUS BAR  (stile MobaXterm)
    # ──────────────────────────────────────────
    def _setup_statusbar(self):
        sb = QStatusBar()
        sb.setStyleSheet(f"""
            QStatusBar {{
                background: #005B9A;
                color: white;
                font-size: 11px;
                border-top: 1px solid #00448A;
                padding: 2px 6px;
            }}
            QStatusBar::item {{ border: none; }}
        """)
        self.setStatusBar(sb)
        self._status_lbl = QLabel("Pronto — Nexus")
        sb.addWidget(self._status_lbl)
        self._conn_lbl = QLabel("Sessioni aperte: 0")
        sb.addPermanentWidget(self._conn_lbl)

    # ──────────────────────────────────────────
    # Logica left-panel tabs
    # ──────────────────────────────────────────
    def _update_welcome(self):
        """Mostra il benvenuto quando nessuna sessione è aperta."""
        has_tabs = self.tab_widget.count() > 0
        self._welcome.setVisible(not has_tabs)
        self.tab_widget.setVisible(has_tabs)

    def _on_tab_changed(self, idx: int):
        pass

    def _on_left_tab(self, idx: int):
        self._left_stack.setCurrentIndex(idx)
        # Aggiorna header contestuale
        _info = [
            ("🖥",  "Sessions",  "Gestione connessioni SSH · RDP · VNC · Telnet",  "#4EC94E"),
            ("🔖",  "Bookmarks", "Connessioni preferite ad accesso rapido",         "#FFC107"),
            ("🔧",  "Tools",     "Port Scanner · Ping Monitor · Network Discovery", "#5BA8E5"),
            ("⚡",  "Macros",    "Comandi automatici da inviare alle sessioni",      "#F5A623"),
        ]
        if 0 <= idx < len(_info):
            icon, name, desc, color = _info[idx]
            self._left_header_icon.setText(icon)
            self._left_header_name.setText(name)
            self._left_header_name.setStyleSheet(
                f"background:transparent; color:{color}; font-size:12px; font-weight:bold;"
            )
            self._left_header_desc.setText(desc)

    # ──────────────────────────────────────────
    # Connessioni
    # ──────────────────────────────────────────
    def _load_connections(self):
        os.makedirs(os.path.dirname(self._conns_path) or ".", exist_ok=True)
        self._root = load_connections(self._conns_path)
        self.tree_panel.load_tree(self._root)
        all_c = self._root.get_all_connections_recursive()
        self.home_panel.set_connections(all_c)
        self._set_status(f"Caricate {len(all_c)} connessioni")
        if hasattr(self, "_tools_panel"):
            self._tools_panel.set_connections(all_c)

    def _save_connections(self):
        os.makedirs(os.path.dirname(self._conns_path) or ".", exist_ok=True)
        save_connections(self._root, self._conns_path)
        self._set_status("Connessioni salvate ✓")
        ToastManager.get_instance().show(
            "success", "Configurazione salvata",
            os.path.basename(self._conns_path), duration=2500
        )

    def _open_file(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Apri file connessioni", "", "XML Files (*.xml);;All Files (*)")
        if path:
            self._conns_path = path
            self._load_connections()

    def _on_import_mobaxterm(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        from config.mobaxterm_importer import import_into_root
        path, _ = QFileDialog.getOpenFileName(
            self, "Importa sessioni MobaXterm", "",
            "MobaXterm Sessions (*.mxtsessions);;All Files (*)")
        if not path:
            return
        try:
            count = import_into_root(self._root, path)
        except Exception as exc:
            QMessageBox.critical(self, "Errore import", str(exc))
            return
        if count == 0:
            QMessageBox.information(self, "Import MobaXterm",
                                    "Nessuna connessione trovata nel file.")
            return
        self.tree_panel.refresh()
        self.home_panel.set_connections(self._root.get_all_connections_recursive())
        if hasattr(self, "_tools_panel"):
            self._tools_panel.set_connections(self._root.get_all_connections_recursive())
        self._save_connections()
        self._set_status(f"Importate {count} connessioni da MobaXterm")
        ToastManager.get_instance().show(
            "success", "Import MobaXterm completato",
            f"{count} connessioni importate"
        )

    def _on_open_connection(self, conn: ConnectionInfo):
        from core.models import ContainerInfo, RootNode
        if isinstance(conn, (ContainerInfo, RootNode)):
            return
        if conn.id in self._open_tabs:
            for i in range(self.tab_widget.count()):
                if self.tab_widget.widget(i) is self._open_tabs[conn.id]:
                    self.tab_widget.setCurrentIndex(i)
                    return
        tab = ConnectionTab(conn, self)
        proto = conn.protocol.value
        icon_map = {"SSH2":"🟢","RDP":"🔵","VNC":"🟠",
                    "HTTP":"🟣","HTTPS":"🟣","Telnet":"🟡"}
        icon = icon_map.get(proto, "⚪")
        name_short = conn.name[:26] + "…" if len(conn.name) > 26 else conn.name
        title = f"{icon} {name_short}"
        idx = self.tab_widget.addTab(tab, title)
        self.tab_widget.setCurrentIndex(idx)
        self._open_tabs[conn.id] = tab
        self._update_welcome()
        ok = tab.connect()
        self._tab_bar._setup_close_buttons()
        if ok:
            self._set_status(f"Connesso a {conn.hostname} [{proto}]")
            ToastManager.get_instance().show(
                "success", "Connessione avviata",
                f"{conn.name}  [{proto}]  {conn.hostname}"
            )
        else:
            self._set_status(f"Connessione a {conn.hostname} in corso...")
        self._update_conn_count()
        self._sync_tree_status()
        self._sessions_bar.refresh(self._open_tabs)

    def _on_select_connection(self, conn):
        from core.models import ContainerInfo, RootNode
        if not isinstance(conn, (ContainerInfo, RootNode)):
            self._set_status(f"{conn.name}  ▸  {conn.hostname}:{conn.port}  [{conn.protocol.value}]")

    def _on_new_connection(self, parent_node=None):
        from ui.dialogs.connection_dialog import ConnectionDialog
        dlg = ConnectionDialog(parent=self)
        if dlg.exec():
            c = dlg.conn
            if isinstance(parent_node, ContainerInfo):
                parent_node.add_child(c)
            else:
                self._root.add_child(c)
            self.tree_panel.refresh()
            self.home_panel.set_connections(self._root.get_all_connections_recursive())
            self._save_connections()

    def _on_new_folder(self, parent_node=None):
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Nuova Cartella", "Nome:")
        if ok and name:
            folder = ContainerInfo(); folder.name = name
            (parent_node if isinstance(parent_node, ContainerInfo) else self._root).add_child(folder)
            self.tree_panel.refresh(); self._save_connections()

    def _on_edit_connection(self, conn):
        from ui.dialogs.connection_dialog import ConnectionDialog
        dlg = ConnectionDialog(connection_info=conn, parent=self)
        if dlg.exec():
            self.tree_panel.refresh()
            self.home_panel.set_connections(self._root.get_all_connections_recursive())
            self._save_connections()

    def _on_delete_connection(self, conn):
        r = QMessageBox.question(self, "Elimina",
            f"Eliminare '{conn.name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            if conn.parent: conn.parent.remove_child(conn)
            self.tree_panel.refresh()
            self.home_panel.set_connections(self._root.get_all_connections_recursive())
            self._save_connections()

    def _on_tab_close(self, idx: int):
        w = self.tab_widget.widget(idx)
        if isinstance(w, HomePanel):
            return
        if isinstance(w, ConnectionTab):
            w.disconnect()
            if w.conn.id in self._open_tabs:
                del self._open_tabs[w.conn.id]
        self.tab_widget.removeTab(idx)
        self._update_conn_count()
        self._update_welcome()
        self._sync_tree_status()
        self._sessions_bar.refresh(self._open_tabs)

    def _on_quick_connect(self):
        text = self.quick_box.text().strip()
        if not text: return
        proto_str = self.proto_combo.currentText()
        username = ""; hostname = text; port = 0
        if "@" in hostname:
            username, hostname = hostname.rsplit("@", 1)
        if ":" in hostname:
            hostname, ps = hostname.rsplit(":", 1)
            try: port = int(ps)
            except: pass
        from core.models import ConnectionInfo, ProtocolType
        c = ConnectionInfo()
        c.name = f"{hostname} [{proto_str}]"
        c.hostname = hostname; c.username = username
        c.protocol = ProtocolType(proto_str)
        c.port = port or c.get_default_port()
        self.quick_box.clear()
        self._on_open_connection(c)

    def _disconnect_current(self):
        self._on_tab_close(self.tab_widget.currentIndex())

    def _close_all_connections(self):
        for i in range(self.tab_widget.count()-1, -1, -1):
            self._on_tab_close(i)

    def _show_dashboard(self):
        """Apre la Dashboard come finestra separata (non modale)."""
        if self._dashboard_window is None:
            # Crea la finestra una sola volta
            self._dashboard_window = QWidget(self)
            self._dashboard_window.setWindowTitle("Nexus — Dashboard Live")
            self._dashboard_window.setWindowFlags(Qt.WindowType.Window)
            self._dashboard_window.resize(1060, 700)
            self._dashboard_window.setStyleSheet(f"background:{BG_COLOR};")
            from ui.icon_generator import create_app_icon
            self._dashboard_window.setWindowIcon(create_app_icon(32))
            lay = QVBoxLayout(self._dashboard_window)
            lay.setContentsMargins(0, 0, 0, 0)
            self._dashboard = DashboardPanel()
            self._dashboard.open_connection.connect(self._on_open_connection)
            lay.addWidget(self._dashboard)

        self._dashboard.set_data(
            self._root.get_all_connections_recursive() if self._root else [],
            self._open_tabs,
        )
        self._dashboard_window.show()
        self._dashboard_window.raise_()
        self._dashboard_window.activateWindow()

    def _show_home(self):
        self._left_stack.setCurrentIndex(0)
        self.vtab._on_click(0)

    # ──────────────────────────────────────────
    # Implementazioni bottoni toolbar
    # ──────────────────────────────────────────

    def _on_add_to_bookmarks(self, conn):
        """Aggiunge una connessione dal tree ai bookmarks."""
        self._bookmarks_panel.add_from_connection(conn)
        self._left_stack.setCurrentIndex(1)
        self.vtab._on_click(1)
        self._set_status(f"'{conn.name}' aggiunto ai bookmark")

    def _on_split(self):
        """Split: apre la stessa connessione corrente in un secondo pane affiancato."""
        current = self.tab_widget.currentWidget()
        if not isinstance(current, ConnectionTab):
            QMessageBox.information(self, "Split", "Apri una connessione prima di usare Split.")
            return
        conn_clone = current.conn.clone()
        self._on_open_connection(conn_clone)

    def _on_multiexec(self):
        """MultiExec: broadcast comando su più sessioni aperte."""
        from ui.dialogs.multiexec_dialog import MultiExecDialog
        dlg = MultiExecDialog(self._open_tabs, self)
        dlg.exec()

    def _on_tunneling(self):
        """Tunneling: port forwarding SSH."""
        from ui.dialogs.tunneling_dialog import TunnelingDialog
        dlg = TunnelingDialog(self._open_tabs, self)
        dlg.exec()

    def _on_show_tools(self):
        """Tools: mostra il pannello port scanner nel tab sinistro."""
        self._left_stack.setCurrentIndex(2)
        self.vtab._on_click(2)

    def _on_xserver(self):
        """X server: tenta di avviare Xming o VcXsrv su Windows."""
        import subprocess, os
        xservers = [
            r"C:\Program Files\Xming\Xming.exe",
            r"C:\Program Files (x86)\Xming\Xming.exe",
            r"C:\Program Files\VcXsrv\vcxsrv.exe",
        ]
        for path in xservers:
            if os.path.exists(path):
                subprocess.Popen([path, ":0", "-multiwindow", "-clipboard", "-wgl"],
                                 creationflags=subprocess.CREATE_NO_WINDOW)
                self._set_status("X server avviato su :0")
                os.environ["DISPLAY"] = "127.0.0.1:0.0"
                return
        QMessageBox.information(self, "X Server",
            "Nessun X server trovato.\n\n"
            "Installa Xming (xming.org) o VcXsrv per il supporto X11.\n\n"
            "Dopo l'installazione, clicca nuovamente questo bottone.")

    def _on_duplicate_session(self):
        """Duplica la sessione corrente aprendo una nuova connessione identica."""
        current = self.tab_widget.currentWidget()
        if isinstance(current, ConnectionTab):
            self._on_open_connection(current.conn.clone())
        else:
            QMessageBox.information(self, "Duplica", "Nessuna sessione attiva da duplicare.")

    def _on_run_macro(self, text: str):
        """Esegui macro sulla sessione corrente."""
        current = self.tab_widget.currentWidget()
        if isinstance(current, ConnectionTab):
            current.send_keys(text)
        else:
            QMessageBox.information(self, "Macro", "Nessuna sessione attiva.")

    def _on_rename_connection(self, conn):
        """Rinomina una connessione con un dialogo inline."""
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(self, "Rinomina connessione",
                                        "Nuovo nome:", text=conn.name)
        if ok and name.strip():
            conn.name = name.strip()
            self.tree_panel.refresh()
            self.home_panel.set_connections(self._root.get_all_connections_recursive())
            self._save_connections()

    # ──────────────────────────────────────────
    # Funzioni admin aziendali
    # ──────────────────────────────────────────

    def _on_user_manager(self):
        from ui.dialogs.user_manager_dialog import UserManagerDialog
        from core.user_manager import UserManager
        u = UserManager.get_instance().current_user()
        if u and not u.can("manage_users"):
            QMessageBox.warning(self, "Accesso negato",
                                "Solo gli amministratori possono gestire gli utenti.")
            return
        dlg = UserManagerDialog(self)
        dlg.exec()

    def _on_session_logs(self):
        from ui.dialogs.session_log_viewer import SessionLogViewer
        dlg = SessionLogViewer(self)
        dlg.exec()

    def _on_report(self):
        from ui.dialogs.report_dialog import ReportDialog
        all_c = self._root.get_all_connections_recursive() if self._root else []
        dlg = ReportDialog(connections=all_c, parent=self)
        dlg.exec()

    def _on_network_discovery(self):
        from ui.dialogs.network_discovery_dialog import NetworkDiscoveryDialog
        dlg = NetworkDiscoveryDialog(self)
        dlg.hosts_to_add.connect(self._on_hosts_discovered)
        dlg.exec()

    def _on_scheduler(self):
        from ui.dialogs.scheduler_dialog import SchedulerDialog
        hosts = [c.hostname for c in self._root.get_all_connections_recursive()
                 if self._root and c.hostname]
        dlg = SchedulerDialog(available_hosts=hosts, parent=self)
        dlg.exec()

    def _on_hosts_discovered(self, hosts: list):
        """Aggiunge gli host scoperti da Network Discovery come nuove connessioni SSH."""
        from core.models import ConnectionInfo, ProtocolType, ContainerInfo
        from core.session_logger import SessionLogger

        # Crea/trova cartella "Discovered"
        discovered_folder = None
        for child in self._root.children:
            if isinstance(child, ContainerInfo) and child.name == "Discovered":
                discovered_folder = child
                break
        if discovered_folder is None:
            discovered_folder = ContainerInfo()
            discovered_folder.name = "Discovered"
            self._root.add_child(discovered_folder)

        proto_map = {22: ProtocolType.SSH2, 23: ProtocolType.Telnet,
                     80: ProtocolType.HTTP, 443: ProtocolType.HTTPS,
                     3389: ProtocolType.RDP, 5900: ProtocolType.VNC,
                     8080: ProtocolType.HTTP}
        added = 0
        for h in hosts:
            c = ConnectionInfo()
            c.hostname = h["ip"]
            c.port     = h["port"]
            c.name     = f"{h['ip']}:{h['port']} ({h['service']})"
            c.protocol = proto_map.get(h["port"], ProtocolType.SSH2)
            discovered_folder.add_child(c)
            added += 1

        self.tree_panel.refresh()
        self.home_panel.set_connections(self._root.get_all_connections_recursive())
        if hasattr(self, "_tools_panel"):
            self._tools_panel.set_connections(self._root.get_all_connections_recursive())
        self._save_connections()
        self._set_status(f"{added} host aggiunti in 'Discovered'")

    def _show_settings(self):
        from ui.dialogs.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self)
        dlg.exec()

    def _start_scheduler(self):
        from core.scheduler import TaskScheduler
        sched = TaskScheduler.get_instance()
        sched.set_execute_callback(self._on_scheduler_task_due)
        sched.start()

    # Pattern comandi pericolosi bloccati dallo scheduler
    _DANGEROUS_CMD = re.compile(
        r'rm\s+(-\w*f\w*\s+/|--no-preserve-root)'    # rm -rf /
        r'|mkfs\b'                                     # formattazione disco
        r'|dd\s+\S*if='                                # dd su device
        r'|>\s*/dev/[sh]d'                             # sovrascrittura device
        r'|curl\s+[^\n]*\|\s*(ba?sh|sh\b)'            # curl | bash
        r'|wget\s+[^\n]*\|\s*(ba?sh|sh\b)'            # wget | sh
        r'|:\(\)\{.*\}.*:',                            # fork bomb
        re.IGNORECASE | re.DOTALL
    )

    def _on_scheduler_task_due(self, task):
        import re as _re
        import socket
        import paramiko
        from core.session_logger import SessionLogger
        from protocols.ssh_protocol import _KNOWN_HOSTS_PATH

        hosts = task.target_hosts
        cmd   = task.command

        # Blocca comandi con pattern pericolosi
        if self._DANGEROUS_CMD.search(cmd):
            SessionLogger.get_instance().log(
                "ERROR", f"scheduler/{task.name}", task.protocol,
                f"[BLOCCATO] pattern pericoloso: {cmd[:120]}"
            )
            from core.scheduler import TaskScheduler
            TaskScheduler.get_instance().mark_ran(
                task.id, "BLOCCATO: pattern pericoloso rilevato"
            )
            ToastManager.get_instance().show(
                "warning", f"Scheduler: {task.name}",
                "Comando bloccato: pattern pericoloso"
            )
            return

        # Log prima dell'esecuzione (audit trail)
        host_list = ", ".join(hosts[:5]) + ("…" if len(hosts) > 5 else "")
        SessionLogger.get_instance().log(
            "COMMAND", f"scheduler/{task.name}", task.protocol,
            f"[AVVIO] cmd={cmd[:80]} hosts=[{host_list}]"
        )

        results = []
        for host in hosts:
            try:
                sock = socket.create_connection((host, 22), timeout=8)
                cli  = paramiko.SSHClient()
                # Usa RejectPolicy: lo scheduler accetta solo host già verificati
                cli.set_missing_host_key_policy(paramiko.RejectPolicy())
                if os.path.exists(_KNOWN_HOSTS_PATH):
                    cli.load_host_keys(_KNOWN_HOSTS_PATH)
                cli.connect(hostname=host, sock=sock, timeout=8,
                            look_for_keys=True, allow_agent=True)
                _, stdout, stderr = cli.exec_command(cmd, timeout=30)
                out = stdout.read().decode(errors="replace").strip()
                err = stderr.read().decode(errors="replace").strip()
                cli.close()
                # Log solo esito (non output — potrebbe contenere segreti)
                esito = "OK" if not err else f"WARN:{err[:40]}"
                results.append(f"{host}: {esito}")
                SessionLogger.get_instance().log(
                    "COMMAND", host, task.protocol,
                    f"[scheduler/{task.name}] esito={esito}"
                )
            except paramiko.SSHException as e:
                msg = str(e)
                if "not found in known_hosts" in msg or "Server" in msg:
                    results.append(
                        f"{host}: BLOCCATO - host non presente in known_hosts"
                    )
                else:
                    results.append(f"{host}: ERRORE SSH - {msg[:60]}")
            except Exception as e:
                results.append(f"{host}: ERRORE - {type(e).__name__}")
        from core.scheduler import TaskScheduler
        summary = "; ".join(results)
        TaskScheduler.get_instance().mark_ran(task.id, summary)
        errors = sum(1 for r in results if "ERRORE" in r)
        if errors:
            ToastManager.get_instance().show(
                "warning", f"Scheduler: {task.name}",
                f"{len(hosts) - errors}/{len(hosts)} host OK"
            )
        else:
            ToastManager.get_instance().show(
                "success", f"Scheduler: {task.name}",
                f"Completato su {len(hosts)} host"
            )

    def _show_about(self):
        QMessageBox.about(self, "Nexus",
            "<b>Nexus</b><br>Multi-protocol remote connection manager<br>"
            "Ispirato a MobaXterm<br><br>"
            "<b>Protocolli:</b> SSH, RDP, VNC, Telnet, HTTP/HTTPS<br>"
            "<b>UI:</b> PyQt6  |  <b>SSH:</b> paramiko")

    def _set_status(self, text: str):
        self._status_lbl.setText(text)

    def _close_by_conn_id(self, conn_id: str):
        tab = self._open_tabs.get(conn_id)
        if tab is None:
            return
        for i in range(self.tab_widget.count()):
            if self.tab_widget.widget(i) is tab:
                self._on_tab_close(i)
                return

    def _sync_tree_status(self):
        """Aggiorna indicatori connesso/ping nell'albero."""
        ids = set(self._open_tabs.keys())
        self.tree_panel.set_connected_ids(ids)

    def _update_conn_count(self):
        self._conn_lbl.setText(f"Sessioni aperte: {len(self._open_tabs)}")

    def _on_host_down(self, host: str, port: int):
        ToastManager.get_instance().show(
            "error", "Host non raggiungibile",
            f"{host}:{port} — connessione persa"
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        ToastManager.get_instance().restack()

    def closeEvent(self, e):
        if self._open_tabs:
            r = QMessageBox.question(self, "Chiudi",
                f"Ci sono {len(self._open_tabs)} sessioni aperte. Chiudere?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if r == QMessageBox.StandardButton.No:
                e.ignore(); return
        if self._dashboard_window:
            self._dashboard_window.close()
        self._close_all_connections()
        self._save_connections()
        e.accept()
