"""
Finestra principale - layout identico a MobaXterm (dark theme).
"""
from __future__ import annotations
import os
import sys
from typing import Dict, Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QTabWidget, QToolBar, QStatusBar, QLabel, QLineEdit,
    QPushButton, QComboBox, QMessageBox, QFrame, QSizePolicy,
    QStackedWidget, QApplication
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal, QTimer
from PyQt6.QtGui import (
    QAction, QFont, QKeySequence, QColor, QPainter,
    QPixmap, QIcon, QLinearGradient
)

from themes.dark_theme import DARK_QSS, ACCENT_COLOR, CARD_COLOR, TEXT_COLOR, SUB_COLOR, BG_COLOR
from ui.connection_tree import ConnectionTreePanel
from ui.home_panel import HomePanel
from core.models import ConnectionInfo, ContainerInfo, RootNode
from config.xml_parser import load_connections, save_connections

# Percorso config: usa prima shared/ (struttura unificata), poi fallback APPDATA
_THIS_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SHARED_XML = os.path.join(_THIS_DIR, "..", "shared", "confCons.xml")
_SHARED_XML = os.path.normpath(_SHARED_XML)

DEFAULT_CONNS_PATH = (
    _SHARED_XML if os.path.isdir(os.path.dirname(_SHARED_XML))
    else os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")),
                      "PyMRemoteNG", "confCons.xml")
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
class VerticalTabBar(QWidget):
    """
    Barra tab verticale sul lato sinistro (Sessions / ★ / Tools / Macros).
    """
    tab_changed = pyqtSignal(int)

    TABS = [
        ("Sessions", "🖥"),
        ("Bookmarks","★"),
        ("Tools",    "🔧"),
        ("Macros",   "●"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(28)
        self.setStyleSheet(f"background-color: #111111; border-right: 1px solid #2A2A2A;")
        self._current = 0
        self._btns: list[QPushButton] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(0)

        for i, (name, icon) in enumerate(self.TABS):
            btn = QPushButton(icon)
            btn.setFixedSize(28, 52)
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            btn.setToolTip(name)
            idx = i
            btn.clicked.connect(lambda _, x=idx: self._on_click(x))
            btn.setStyleSheet(f"""
                QPushButton {{
                    background: transparent;
                    color: {SUB_COLOR};
                    border: none;
                    font-size: 15px;
                    border-left: 2px solid transparent;
                }}
                QPushButton:hover {{
                    background: #1E1E1E;
                    color: {TEXT_COLOR};
                }}
                QPushButton:checked {{
                    background: #1A1A1A;
                    color: {ACCENT_COLOR};
                    border-left: 2px solid {ACCENT_COLOR};
                }}
            """)
            layout.addWidget(btn)
            self._btns.append(btn)

        layout.addStretch()

    def _on_click(self, idx: int):
        self._current = idx
        for i, b in enumerate(self._btns):
            b.setChecked(i == idx)
        self.tab_changed.emit(idx)


# ─────────────────────────────────────────────────────────────
# Finestra principale
# ─────────────────────────────────────────────────────────────
class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()
        self._root: RootNode   = RootNode()
        self._open_tabs: Dict[str, ConnectionTab] = {}
        self._conns_path = DEFAULT_CONNS_PATH

        self.setWindowTitle("PyMRemoteNG")
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
        m2.addAction("Importa sessioni...", self._open_file)
        m2.addSeparator()
        m2.addAction("Chiudi tutte le sessioni", self._close_all_connections)

        # View
        m3 = menu("View")
        m3.addAction("Home", self._show_home)
        m3.addAction("Pannello sessioni", lambda: self._left_stack.setCurrentIndex(0))

        # Tools
        m4 = menu("Tools")
        m4.addAction("Impostazioni", self._show_settings)

        # Settings
        m5 = menu("Settings")
        m5.addAction("Configurazione...", self._show_settings)

        # Help
        m6 = menu("Help")
        m6.addAction("Informazioni", self._show_about)

    # ──────────────────────────────────────────
    # TOOLBAR ICONE GRANDI  (stile MobaXterm)
    # ──────────────────────────────────────────
    def _setup_toolbar(self):
        tb = QToolBar()
        tb.setMovable(False)
        tb.setFloatable(False)
        tb.setIconSize(QSize(32, 32))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        tb.setStyleSheet(f"""
            QToolBar {{
                background-color: #191919;
                border: none;
                border-bottom: 1px solid #2A2A2A;
                spacing: 1px;
                padding: 3px 6px 3px 6px;
            }}
            QToolButton {{
                background: transparent;
                color: {TEXT_COLOR};
                border: none;
                border-radius: 3px;
                padding: 4px 6px 2px 6px;
                font-size: 11px;
                min-width: 52px;
            }}
            QToolButton:hover  {{ background: #2A2A2A; }}
            QToolButton:pressed {{ background: {ACCENT_COLOR}; color: white; }}
            QToolBar::separator {{
                background: #333;
                width: 1px;
                margin: 6px 3px;
            }}
        """)

        def _ico(emoji: str, bg: str = "#1E3A2A", fg: str = "#4EC94E") -> QIcon:
            px = QPixmap(32, 32)
            px.fill(QColor(bg))
            p = QPainter(px)
            p.setFont(QFont("Segoe UI Emoji", 16))
            p.setPen(QColor(fg))
            p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, emoji)
            p.end()
            return QIcon(px)

        def btn(label: str, emoji: str, bg: str, cb, shortcut: str = ""):
            act = QAction(_ico(emoji, bg), label, self)
            if shortcut:
                act.setShortcut(shortcut)
            act.triggered.connect(cb)
            tb.addAction(act)
            return act

        btn("Session",    "＋",  "#1E3A2A", lambda: self._on_new_connection(None), "Ctrl+N")
        tb.addSeparator()
        btn("Sessions",   "🗂",  "#1A2A3A", self._show_home)
        btn("Split",      "⊞",  "#2A1A3A", self._on_split)
        btn("MultiExec",  "⚡",  "#2A2A1A", self._on_multiexec)
        tb.addSeparator()
        btn("Tunneling",  "🔗",  "#1A1A3A", self._on_tunneling)
        btn("Tools",      "🔧",  "#2A1A1A", self._on_show_tools)
        btn("Settings",   "⚙",  "#1A1A1A", self._show_settings)
        tb.addSeparator()
        btn("Save",       "💾",  "#1A2A1A", self._save_connections, "Ctrl+S")
        btn("Open",       "📂",  "#2A2A1A", self._open_file)

        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        spacer.setStyleSheet("background: transparent;")
        tb.addWidget(spacer)

        # X server + Exit (a destra, come MobaXterm)
        btn("X server",   "✕",  "#1A1A2A", self._on_xserver)
        tb.addSeparator()
        btn("Exit",       "⏻",  "#3A1A1A", self.close)

        self.addToolBar(tb)

    # ──────────────────────────────────────────
    # QUICK CONNECT BAR  (riga sotto toolbar)
    # ──────────────────────────────────────────
    def _setup_quickconnect_bar(self):
        bar = QWidget()
        bar.setFixedHeight(32)
        bar.setStyleSheet(f"background-color: #141414; border-bottom: 1px solid #2A2A2A;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 2, 8, 2)
        layout.setSpacing(6)

        lbl = QLabel("Quick connect")
        lbl.setStyleSheet(f"color: {SUB_COLOR}; font-size: 11px; background: transparent;")
        layout.addWidget(lbl)

        self.quick_box = QLineEdit()
        self.quick_box.setPlaceholderText("utente@host  o  host:porta")
        self.quick_box.setFixedWidth(260)
        self.quick_box.setFixedHeight(24)
        self.quick_box.setStyleSheet(f"""
            QLineEdit {{
                background: #1E1E1E; color: {TEXT_COLOR};
                border: 1px solid #333; border-radius: 3px;
                padding: 2px 8px; font-size: 12px;
            }}
            QLineEdit:focus {{ border-color: {ACCENT_COLOR}; }}
        """)
        self.quick_box.returnPressed.connect(self._on_quick_connect)
        layout.addWidget(self.quick_box)

        from core.models import ProtocolType
        self.proto_combo = QComboBox()
        for p in [ProtocolType.SSH2, ProtocolType.RDP, ProtocolType.VNC,
                  ProtocolType.Telnet, ProtocolType.HTTP, ProtocolType.HTTPS]:
            self.proto_combo.addItem(p.value)
        self.proto_combo.setFixedHeight(24)
        self.proto_combo.setStyleSheet(f"""
            QComboBox {{
                background: #1E1E1E; color: {TEXT_COLOR};
                border: 1px solid #333; border-radius: 3px;
                padding: 1px 6px; min-width: 70px; font-size: 12px;
            }}
            QComboBox QAbstractItemView {{
                background: #1E1E1E; color: {TEXT_COLOR};
                selection-background-color: {ACCENT_COLOR};
            }}
            QComboBox::drop-down {{ border: none; width: 16px; }}
        """)
        layout.addWidget(self.proto_combo)

        go_btn = QPushButton("▶  Connetti")
        go_btn.setFixedHeight(24)
        go_btn.setStyleSheet(f"""
            QPushButton {{
                background: {ACCENT_COLOR}; color: white;
                border: none; border-radius: 3px;
                padding: 0 14px; font-size: 12px; font-weight: bold;
            }}
            QPushButton:hover  {{ background: #0088DD; }}
            QPushButton:pressed {{ background: #005A9E; }}
        """)
        go_btn.clicked.connect(self._on_quick_connect)
        layout.addWidget(go_btn)
        layout.addStretch()

        # Aggiungi come widget toolbar aggiuntiva
        qc_bar = QToolBar("QuickConnect")
        qc_bar.setMovable(False)
        qc_bar.setStyleSheet("QToolBar { border: none; padding: 0; }")
        qc_bar.addWidget(bar)
        self.addToolBar(qc_bar)

    # ──────────────────────────────────────────
    # WIDGET CENTRALE  (splitter MobaXterm)
    # ──────────────────────────────────────────
    def _setup_central(self):
        root = QWidget()
        root.setStyleSheet(f"background: {BG_COLOR};")
        h_layout = QHBoxLayout(root)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)
        self.setCentralWidget(root)

        # ── Tab verticali sx (icone) ──
        self.vtab = VerticalTabBar()
        self.vtab.tab_changed.connect(self._on_left_tab)
        h_layout.addWidget(self.vtab)

        # ── Splitter: pannello sessioni | area centrale ──
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setHandleWidth(1)
        self.splitter.setStyleSheet("QSplitter::handle { background: #2A2A2A; }")
        h_layout.addWidget(self.splitter)

        # ── Pannello sinistro (sessioni / strumenti / macros) ──
        self._left_stack = QStackedWidget()
        self._left_stack.setMinimumWidth(180)
        self._left_stack.setMaximumWidth(380)
        self._left_stack.setStyleSheet(f"background: #111111; border-right: 1px solid #2A2A2A;")

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

        # Pagina 2: Tools (port scanner, keygen, ecc.)
        from ui.tools_panel import ToolsPanel
        self._left_stack.addWidget(ToolsPanel())

        # Pagina 3: Macros
        from ui.macros_panel import MacrosPanel
        self._macros_panel = MacrosPanel()
        self._macros_panel.run_macro.connect(self._on_run_macro)
        self._left_stack.addWidget(self._macros_panel)

        self.splitter.addWidget(self._left_stack)

        # ── Area centrale: tab sessioni ──
        right = QWidget()
        right.setStyleSheet(f"background: {BG_COLOR};")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        self.tab_widget = QTabWidget()
        self.tab_widget.setTabsClosable(True)
        self.tab_widget.setMovable(True)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.tabCloseRequested.connect(self._on_tab_close)
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                background: {BG_COLOR};
                border: none;
            }}
            QTabBar {{
                background: #141414;
                border-bottom: 1px solid #2A2A2A;
            }}
            QTabBar::tab {{
                background: #141414;
                color: {SUB_COLOR};
                border: none;
                border-right: 1px solid #2A2A2A;
                padding: 6px 18px 6px 14px;
                font-size: 12px;
                min-width: 90px;
                max-width: 200px;
            }}
            QTabBar::tab:selected {{
                background: {BG_COLOR};
                color: {TEXT_COLOR};
                border-bottom: 2px solid {ACCENT_COLOR};
            }}
            QTabBar::tab:hover:!selected {{
                background: #1E1E1E;
                color: {TEXT_COLOR};
            }}
            QTabBar::close-button {{
                image: none;
                subcontrol-position: right;
                padding: 2px;
            }}
        """)
        # Widget di benvenuto (mostrato quando non ci sono sessioni aperte)
        self._welcome = QLabel(
            "← Seleziona una connessione nel pannello di sinistra\n"
            "oppure usa Quick Connect per avviare una nuova sessione"
        )
        self._welcome.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._welcome.setWordWrap(True)
        self._welcome.setStyleSheet(
            f"color: {SUB_COLOR}; font-size: 14px; background: {BG_COLOR}; padding: 40px;")
        right_layout.addWidget(self._welcome)
        right_layout.addWidget(self.tab_widget)
        self.splitter.addWidget(right)
        self.splitter.setSizes([240, 1000])

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
        self._status_lbl = QLabel("Pronto — PyMRemoteNG")
        sb.addWidget(self._status_lbl)
        self._conn_lbl = QLabel("Sessioni aperte: 0")
        sb.addPermanentWidget(self._conn_lbl)

    # ──────────────────────────────────────────
    # Logica left-panel tabs
    # ──────────────────────────────────────────
    def _update_welcome(self):
        """Mostra benvenuto quando nessuna sessione è aperta, tab widget altrimenti."""
        has_tabs = self.tab_widget.count() > 0
        self._welcome.setVisible(not has_tabs)
        self.tab_widget.setVisible(has_tabs)

    def _on_left_tab(self, idx: int):
        self._left_stack.setCurrentIndex(idx)

    # ──────────────────────────────────────────
    # Connessioni
    # ──────────────────────────────────────────
    def _load_connections(self):
        os.makedirs(os.path.dirname(self._conns_path), exist_ok=True)
        self._root = load_connections(self._conns_path)
        self.tree_panel.load_tree(self._root)
        all_c = self._root.get_all_connections_recursive()
        self.home_panel.set_connections(all_c)
        self._set_status(f"Caricate {len(all_c)} connessioni")

    def _save_connections(self):
        os.makedirs(os.path.dirname(self._conns_path), exist_ok=True)
        save_connections(self._root, self._conns_path)
        self._set_status("Connessioni salvate ✓")

    def _open_file(self):
        from PyQt6.QtWidgets import QFileDialog
        path, _ = QFileDialog.getOpenFileName(
            self, "Apri file connessioni", "", "XML Files (*.xml);;All Files (*)")
        if path:
            self._conns_path = path
            self._load_connections()

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
        icon_map = {"SSH2":"🟢","SSH1":"🟢","RDP":"🔵","VNC":"🟠",
                    "HTTP":"🟣","HTTPS":"🟣","Telnet":"🟡"}
        icon = icon_map.get(proto, "⚪")
        title = f"{icon} {conn.name}"
        idx = self.tab_widget.addTab(tab, title)
        self.tab_widget.setCurrentIndex(idx)
        self._open_tabs[conn.id] = tab
        self._update_welcome()
        ok = tab.connect()
        if ok:
            self._set_status(f"Connesso a {conn.hostname} [{proto}]")
        else:
            self._set_status(f"Connessione a {conn.hostname} in corso...")
        self._update_conn_count()

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

    def _show_home(self):
        # Con il nuovo layout le connessioni sono nel pannello sinistro;
        # il bottone "Sessions" porta al pannello Sessions (indice 0)
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

    def _show_settings(self):
        from ui.dialogs.settings_dialog import SettingsDialog
        dlg = SettingsDialog(self)
        dlg.exec()

    def _show_about(self):
        QMessageBox.about(self, "PyMRemoteNG",
            "<b>PyMRemoteNG</b><br>Multi-protocol remote connection manager<br>"
            "Ispirato a MobaXterm<br><br>"
            "<b>Protocolli:</b> SSH2, SSH1, RDP, VNC, Telnet, HTTP/HTTPS<br>"
            "<b>UI:</b> PyQt6  |  <b>SSH:</b> paramiko")

    def _set_status(self, text: str):
        self._status_lbl.setText(text)

    def _update_conn_count(self):
        self._conn_lbl.setText(f"Sessioni aperte: {len(self._open_tabs)}")

    def closeEvent(self, e):
        if self._open_tabs:
            r = QMessageBox.question(self, "Chiudi",
                f"Ci sono {len(self._open_tabs)} sessioni aperte. Chiudere?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if r == QMessageBox.StandardButton.No:
                e.ignore(); return
        self._close_all_connections()
        self._save_connections()
        e.accept()
