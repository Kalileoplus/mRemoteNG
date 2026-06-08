"""
Dashboard Live — schermata principale con:
  • Stat card (sessioni, connessioni, eventi log, errori)
  • Sessioni attive con accesso rapido
  • Distribuzione protocolli (pill chart)
  • Log recenti (ultime 24h)
Aggiornamento automatico ogni 8 secondi.
"""
from __future__ import annotations
from collections import Counter
from datetime import datetime
from typing import Dict, List

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QTableWidget, QTableWidgetItem,
    QHeaderView, QSizePolicy
)
from themes.dark_theme import ACCENT_COLOR, BG_COLOR, CARD_COLOR, TEXT_COLOR, SUB_COLOR

_PROTO_COLOR = {
    "SSH2": "#4EC94E", "SSH1": "#4EC94E",
    "RDP":  "#4E9EEC",
    "VNC":  "#EC8C4E", "ARD": "#EC8C4E",
    "HTTP": "#A78FEC", "HTTPS": "#A78FEC",
    "Telnet": "#E0C44E", "RAW": "#888888",
}

_EVENT_COLOR = {
    "CONNECT":    "#4EC94E",
    "DISCONNECT": "#FFC107",
    "COMMAND":    "#5BA8E5",
    "ERROR":      "#EF5350",
    "AUTH":       "#9B7FE8",
}


# ── Stat Card ─────────────────────────────────────────────────────────────────

class _StatCard(QFrame):
    def __init__(self, label: str, color: str, icon: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(88)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(f"""
            QFrame {{
                background:#0A0A0A;
                border:1px solid #1C1C1C;
                border-top:3px solid {color};
                border-radius:6px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 10, 16, 10)
        lay.setSpacing(4)

        top = QHBoxLayout()
        ico = QLabel(icon)
        ico.setStyleSheet(f"font-size:16px; color:{color}; background:transparent; border:none;")
        top.addWidget(ico)
        top.addStretch()
        lay.addLayout(top)

        self._val = QLabel("—")
        self._val.setFont(QFont("Segoe UI", 24, QFont.Weight.Bold))
        self._val.setStyleSheet(f"color:{color}; background:transparent; border:none;")
        lay.addWidget(self._val)

        lbl = QLabel(label)
        lbl.setFont(QFont("Segoe UI", 9))
        lbl.setStyleSheet(f"color:{SUB_COLOR}; background:transparent; border:none;")
        lay.addWidget(lbl)

    def set(self, v):
        self._val.setText(str(v))


# ── Session Row ───────────────────────────────────────────────────────────────

class _SessionRow(QFrame):
    go_clicked = pyqtSignal(object)   # ConnectionInfo

    def __init__(self, conn, color: str, parent=None):
        super().__init__(parent)
        self.setFixedHeight(40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._conn = conn
        self.setStyleSheet(f"""
            QFrame {{
                background:#0D0D0D;
                border:1px solid #1A1A1A;
                border-left:4px solid {color};
                border-radius:4px;
            }}
            QFrame:hover {{ background:#141414; border-color:#252525; border-left-color:{color}; }}
        """)
        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 0, 10, 0)
        lay.setSpacing(10)

        badge = QLabel(conn.protocol.value if hasattr(conn.protocol, "value") else "?")
        badge.setFixedWidth(40)
        badge.setFont(QFont("Segoe UI", 8, QFont.Weight.Bold))
        badge.setStyleSheet(f"color:{color}; background:transparent; border:none;")
        lay.addWidget(badge)

        name = QLabel(conn.name[:40])
        name.setFont(QFont("Segoe UI", 10))
        name.setStyleSheet(f"color:{TEXT_COLOR}; background:transparent; border:none;")
        lay.addWidget(name, 1)

        host = QLabel(f"{conn.hostname or ''}:{conn.port}")
        host.setFont(QFont("Cascadia Code,Consolas", 9))
        host.setStyleSheet(f"color:{SUB_COLOR}; background:transparent; border:none;")
        lay.addWidget(host)

        btn = QPushButton("→")
        btn.setFixedSize(24, 24)
        btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{color}; border:1px solid {color}55;
                border-radius:3px; font-size:12px; font-weight:bold; }}
            QPushButton:hover {{ background:{color}22; }}
        """)
        btn.clicked.connect(lambda: self.go_clicked.emit(self._conn))
        lay.addWidget(btn)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            self.go_clicked.emit(self._conn)
        super().mousePressEvent(ev)


# ── Dashboard Panel ───────────────────────────────────────────────────────────

class DashboardPanel(QWidget):
    open_connection = pyqtSignal(object)   # emette ConnectionInfo

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"background:{BG_COLOR};")
        self._connections: List = []
        self._open_tabs:   Dict = {}
        self._setup_ui()

        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(8000)

    # ── UI ────────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        hdr = QWidget()
        hdr.setFixedHeight(44)
        hdr.setStyleSheet("background:#091409; border-bottom:1px solid #1A2A1A;")
        hl = QHBoxLayout(hdr)
        hl.setContentsMargins(16, 0, 12, 0)
        hl.setSpacing(8)
        for txt, style in [
            ("📊", "font-size:17px; background:transparent;"),
            ("Dashboard Live", f"color:{ACCENT_COLOR}; font-size:12px; font-weight:bold; background:transparent;"),
        ]:
            lbl = QLabel(txt)
            lbl.setStyleSheet(style)
            hl.addWidget(lbl)
        hl.addStretch()
        self._ts_lbl = QLabel("")
        self._ts_lbl.setStyleSheet(f"color:{SUB_COLOR}; font-size:10px; background:transparent;")
        hl.addWidget(self._ts_lbl)
        ref = QPushButton("⟳  Aggiorna")
        ref.setFixedHeight(26)
        ref.setStyleSheet(f"""
            QPushButton {{ background:{ACCENT_COLOR}; color:white; border:none;
                border-radius:3px; padding:0 12px; font-size:11px; }}
            QPushButton:hover {{ background:#0088DD; }}
        """)
        ref.clicked.connect(self.refresh)
        hl.addWidget(ref)
        root.addWidget(hdr)

        # Scroll body
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background:{BG_COLOR}; border:none;")
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        body = QWidget()
        body.setStyleSheet(f"background:{BG_COLOR};")
        bl = QVBoxLayout(body)
        bl.setContentsMargins(20, 20, 20, 20)
        bl.setSpacing(22)

        # ── Stat cards ──
        cards = QHBoxLayout()
        cards.setSpacing(12)
        self._c_sess  = _StatCard("Sessioni aperte",    "#4EC94E", "🔌")
        self._c_conns = _StatCard("Connessioni totali", "#5BA8E5", "🗄")
        self._c_today = _StatCard("Eventi oggi",        "#FFC107", "📋")
        self._c_err   = _StatCard("Errori oggi",        "#EF5350", "⚠")
        for c in [self._c_sess, self._c_conns, self._c_today, self._c_err]:
            cards.addWidget(c)
        bl.addLayout(cards)

        # ── Sessioni attive ──
        bl.addWidget(self._sep_title("🔌  Sessioni attive"))
        self._sess_container = QWidget()
        self._sess_container.setStyleSheet(f"background:{BG_COLOR};")
        self._sess_lay = QVBoxLayout(self._sess_container)
        self._sess_lay.setContentsMargins(0, 0, 0, 0)
        self._sess_lay.setSpacing(4)
        bl.addWidget(self._sess_container)

        # ── Protocolli ──
        bl.addWidget(self._sep_title("📡  Distribuzione protocolli"))
        self._proto_row = QWidget()
        self._proto_row.setStyleSheet(f"background:{BG_COLOR};")
        self._proto_lay = QHBoxLayout(self._proto_row)
        self._proto_lay.setContentsMargins(0, 0, 0, 0)
        self._proto_lay.setSpacing(8)
        self._proto_lay.addStretch()
        bl.addWidget(self._proto_row)

        # ── Log recenti ──
        bl.addWidget(self._sep_title("📋  Log recenti (ultimi 30 eventi)"))
        self._log_table = QTableWidget(0, 5)
        self._log_table.setHorizontalHeaderLabels(
            ["Timestamp", "Tipo", "Utente", "Host", "Protocollo"])
        h = self._log_table.horizontalHeader()
        h.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self._log_table.setColumnWidth(0, 148)
        self._log_table.setColumnWidth(1, 100)
        self._log_table.setColumnWidth(2, 90)
        self._log_table.setColumnWidth(4, 80)
        self._log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._log_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._log_table.verticalHeader().setVisible(False)
        self._log_table.setShowGrid(False)
        self._log_table.setAlternatingRowColors(True)
        self._log_table.setMaximumHeight(280)
        self._log_table.setStyleSheet(f"""
            QTableWidget {{
                background:#080808; color:{TEXT_COLOR};
                border:1px solid #1A1A1A; border-radius:4px;
                alternate-background-color:#0C0C0C;
            }}
            QHeaderView::section {{
                background:#111111; color:{SUB_COLOR};
                border:none; border-bottom:1px solid #1A1A1A;
                padding:5px 8px; font-size:11px;
            }}
            QTableWidget::item {{ padding:0 4px; }}
            QTableWidget::item:selected {{ background:#1A3A5A; color:white; }}
            QScrollBar:vertical {{ background:#0A0A0A; width:6px; border:none; }}
            QScrollBar::handle:vertical {{ background:#2A2A2A; border-radius:3px; }}
        """)
        bl.addWidget(self._log_table)
        bl.addStretch()

        scroll.setWidget(body)
        root.addWidget(scroll)

    def _sep_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        lbl.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        lbl.setStyleSheet(
            f"color:{TEXT_COLOR}; background:transparent;"
            f"border-bottom:1px solid #1A1A1A; padding-bottom:4px;"
        )
        return lbl

    # ── Public API ────────────────────────────────────────────────────────────

    def set_data(self, connections: list, open_tabs: dict):
        self._connections = connections or []
        self._open_tabs   = open_tabs   or {}
        self.refresh()

    def refresh(self):
        self._ts_lbl.setText(
            f"Aggiornato {datetime.now().strftime('%H:%M:%S')}"
        )
        self._refresh_stats()
        self._refresh_sessions()
        self._refresh_protos()
        self._refresh_log()

    # ── Internals ─────────────────────────────────────────────────────────────

    def _refresh_stats(self):
        self._c_sess.set(len(self._open_tabs))
        self._c_conns.set(len(self._connections))
        events = self._get_log_events()
        today  = datetime.now().date().isoformat()
        ev_today = [e for e in events if e.ts.startswith(today)]
        self._c_today.set(len(ev_today))
        self._c_err.set(sum(1 for e in ev_today if e.type == "ERROR"))

    def _refresh_sessions(self):
        _clear_layout(self._sess_lay)
        if not self._open_tabs:
            lbl = QLabel("Nessuna sessione attiva")
            lbl.setStyleSheet(
                f"color:{SUB_COLOR}; font-size:11px; background:transparent; padding:4px 0;"
            )
            self._sess_lay.addWidget(lbl)
            return
        for tab in self._open_tabs.values():
            conn  = tab.conn
            proto = conn.protocol.value if hasattr(conn.protocol, "value") else "?"
            color = _PROTO_COLOR.get(proto, "#888")
            row   = _SessionRow(conn, color)
            row.go_clicked.connect(self.open_connection)
            self._sess_lay.addWidget(row)

    def _refresh_protos(self):
        _clear_layout(self._proto_lay, keep_stretch=True)
        if not self._connections:
            return
        counts = Counter(
            (c.protocol.value if hasattr(c.protocol, "value") else "?")
            for c in self._connections
        )
        total = len(self._connections)
        for proto, n in sorted(counts.items(), key=lambda x: -x[1]):
            color = _PROTO_COLOR.get(proto, "#888")
            pill  = _ProtoPill(proto, n, total, color)
            self._proto_lay.insertWidget(self._proto_lay.count() - 1, pill)

    def _refresh_log(self):
        events = self._get_log_events()[:30]
        self._log_table.setRowCount(0)
        mono = QFont("Cascadia Code,Consolas", 9)
        for ev in events:
            row = self._log_table.rowCount()
            self._log_table.insertRow(row)
            color = _EVENT_COLOR.get(ev.type, "#888")
            for col, txt in enumerate([ev.ts, ev.type, ev.user, ev.host, ev.protocol]):
                item = QTableWidgetItem(txt)
                item.setFont(mono)
                if col == 1:
                    item.setForeground(QColor(color))
                self._log_table.setItem(row, col, item)
            self._log_table.setRowHeight(row, 22)

    def _get_log_events(self) -> list:
        try:
            from core.session_logger import SessionLogger
            return SessionLogger.get_instance().get_all(days=1)
        except Exception:
            return []


# ── Proto Pill ────────────────────────────────────────────────────────────────

class _ProtoPill(QFrame):
    def __init__(self, proto: str, count: int, total: int, color: str, parent=None):
        super().__init__(parent)
        self.setFixedSize(88, 56)
        pct = count / total * 100 if total else 0
        self.setStyleSheet(f"""
            QFrame {{
                background:#0A0A0A;
                border:1px solid {color}33;
                border-top:3px solid {color};
                border-radius:5px;
            }}
        """)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(1)

        v = QLabel(str(count))
        v.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        v.setStyleSheet(f"color:{color}; background:transparent; border:none;")
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(v)

        p = QLabel(f"{proto}  {pct:.0f}%")
        p.setFont(QFont("Segoe UI", 8))
        p.setStyleSheet(f"color:{SUB_COLOR}; background:transparent; border:none;")
        p.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(p)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clear_layout(lay, keep_stretch: bool = False):
    """Svuota un layout, opzionalmente preservando lo stretch finale."""
    while lay.count():
        if keep_stretch and lay.count() == 1:
            item = lay.itemAt(0)
            if item and item.spacerItem():
                break
        item = lay.takeAt(0)
        if item and item.widget():
            item.widget().deleteLater()
