"""
Schermata Home - equivalente di HomeWindow.cs, stile MobaXterm.
"""
from __future__ import annotations
from typing import TYPE_CHECKING, Callable

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QScrollArea, QFrame, QGridLayout, QSizePolicy
)
from PyQt6.QtCore import Qt, pyqtSignal, QSize
from PyQt6.QtGui import QFont, QColor, QPalette, QIcon
from themes.dark_theme import ACCENT_COLOR, BG_COLOR, CARD_COLOR, TEXT_COLOR, SUB_COLOR

if TYPE_CHECKING:
    from core.models import ConnectionInfo


class ConnectionCard(QFrame):
    """Card cliccabile per una connessione recente."""
    clicked = pyqtSignal(object)  # ConnectionInfo

    PROTO_COLORS = {
        "RDP":  "#007ACC",
        "SSH2": "#00AA44",
        "SSH1": "#00AA44",
        "VNC":  "#AA5500",
        "HTTP": "#AA0099",
        "HTTPS":"#AA0099",
        "Telnet": "#777700",
    }

    def __init__(self, conn: 'ConnectionInfo'):
        super().__init__()
        self.conn = conn
        self.setFixedSize(200, 80)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_ui()
        self._set_style(False)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(2)

        proto = self.conn.protocol.value
        color = self.PROTO_COLORS.get(proto, ACCENT_COLOR)

        proto_lbl = QLabel(proto)
        proto_lbl.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        proto_lbl.setStyleSheet(f"color: {color}; background: transparent;")
        layout.addWidget(proto_lbl)

        name_lbl = QLabel(self.conn.name[:24] + ("…" if len(self.conn.name) > 24 else ""))
        name_lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        name_lbl.setStyleSheet(f"color: {TEXT_COLOR}; background: transparent;")
        layout.addWidget(name_lbl)

        host = self.conn.hostname or ""
        host_lbl = QLabel((host[:28] + "…") if len(host) > 28 else host)
        host_lbl.setFont(QFont("Segoe UI", 9))
        host_lbl.setStyleSheet(f"color: {SUB_COLOR}; background: transparent;")
        layout.addWidget(host_lbl)

    def _set_style(self, hovered: bool):
        bg = "#282828" if hovered else CARD_COLOR
        self.setStyleSheet(f"""
            QFrame {{
                background-color: {bg};
                border: 1px solid #2A2A2A;
                border-radius: 4px;
            }}
        """)

    def enterEvent(self, e):
        self._set_style(True)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._set_style(False)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.conn)
        super().mousePressEvent(e)


class HomePanel(QWidget):
    """
    Schermata di benvenuto ispirata a MobaXterm.
    Segnali:
      - new_connection_requested
      - open_connection_requested(ConnectionInfo)
    """
    new_connection_requested = pyqtSignal()
    open_connection_requested = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background-color: {BG_COLOR};")
        self._all_connections: list['ConnectionInfo'] = []
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Contenuto scrollabile centrato
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background-color: {BG_COLOR}; border: none;")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        content = QWidget()
        content.setStyleSheet(f"background-color: {BG_COLOR};")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(40, 60, 40, 40)
        content_layout.setSpacing(0)

        # ── Logo + Titolo ──
        title_row = QHBoxLayout()
        title_row.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title_lbl = QLabel("PyMRemoteNG")
        title_lbl.setFont(QFont("Segoe UI", 32, QFont.Weight.Bold))
        title_lbl.setStyleSheet(f"color: {TEXT_COLOR}; background: transparent;")
        title_row.addWidget(title_lbl)
        content_layout.addLayout(title_row)

        subtitle = QLabel("Multi-protocol remote connection manager")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setFont(QFont("Segoe UI", 12))
        subtitle.setStyleSheet(f"color: {SUB_COLOR}; background: transparent; margin-bottom: 40px;")
        content_layout.addWidget(subtitle)

        # ── Bottoni principali ──
        btn_row = QHBoxLayout()
        btn_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_row.setSpacing(16)

        self.btn_new = QPushButton("  +  Nuova Connessione")
        self.btn_new.setFixedSize(230, 52)
        self.btn_new.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        self.btn_new.setStyleSheet(f"""
            QPushButton {{
                background-color: {ACCENT_COLOR};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 0 20px;
            }}
            QPushButton:hover {{
                background-color: #0088DD;
            }}
            QPushButton:pressed {{
                background-color: #005A9E;
            }}
        """)
        self.btn_new.clicked.connect(self.new_connection_requested.emit)
        btn_row.addWidget(self.btn_new)

        content_layout.addLayout(btn_row)
        content_layout.addSpacing(40)

        # ── Barra di ricerca ──
        search_container = QHBoxLayout()
        search_container.setAlignment(Qt.AlignmentFlag.AlignCenter)

        search_frame = QFrame()
        search_frame.setFixedWidth(500)
        search_frame.setFixedHeight(42)
        search_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {CARD_COLOR};
                border: 1px solid #2A2A2A;
                border-radius: 4px;
            }}
        """)
        search_inner = QHBoxLayout(search_frame)
        search_inner.setContentsMargins(10, 0, 10, 0)

        search_icon = QLabel("🔍")
        search_icon.setStyleSheet(f"background: transparent; color: {SUB_COLOR}; font-size: 14px;")
        search_inner.addWidget(search_icon)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Cerca sessione o nome server...")
        self.search_box.setStyleSheet(f"""
            QLineEdit {{
                background: transparent;
                color: {TEXT_COLOR};
                border: none;
                font-size: 12px;
                padding: 4px;
            }}
        """)
        self.search_box.textChanged.connect(self._filter_connections)
        search_inner.addWidget(self.search_box)
        search_container.addWidget(search_frame)
        content_layout.addLayout(search_container)
        content_layout.addSpacing(30)

        # ── Sezione sessioni recenti ──
        recent_header = QLabel("Sessioni Salvate")
        recent_header.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        recent_header.setStyleSheet(f"color: {SUB_COLOR}; background: transparent; margin-bottom: 12px;")
        content_layout.addWidget(recent_header)

        self.cards_layout = QGridLayout()
        self.cards_layout.setSpacing(10)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
        content_layout.addLayout(self.cards_layout)

        self.empty_label = QLabel("Nessuna connessione salvata.\nClicca '+ Nuova Connessione' per iniziare.")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.setFont(QFont("Segoe UI", 11))
        self.empty_label.setStyleSheet(f"color: {SUB_COLOR}; background: transparent; padding: 30px;")
        content_layout.addWidget(self.empty_label)

        content_layout.addStretch()
        scroll.setWidget(content)
        main_layout.addWidget(scroll)

    def set_connections(self, connections: list['ConnectionInfo']):
        self._all_connections = connections
        self._filter_connections(self.search_box.text())

    def _filter_connections(self, text: str):
        # Pulisci grid
        while self.cards_layout.count():
            item = self.cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        t = text.lower()
        filtered = [c for c in self._all_connections
                    if not t or
                    t in c.name.lower() or
                    t in (c.hostname or "").lower()]

        if not filtered:
            self.empty_label.setVisible(True)
            return

        self.empty_label.setVisible(False)
        cols = max(1, min(6, len(filtered)))
        for i, conn in enumerate(filtered[:30]):
            card = ConnectionCard(conn)
            card.clicked.connect(self.open_connection_requested.emit)
            self.cards_layout.addWidget(card, i // cols, i % cols)
