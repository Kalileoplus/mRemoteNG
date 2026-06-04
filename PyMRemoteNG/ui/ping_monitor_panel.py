"""
Ping Monitor Panel: mostra stato in tempo reale di tutti gli host.
Verde = raggiungibile, Rosso = non raggiungibile, Grigio = non controllato.
"""
from __future__ import annotations
import socket
import threading
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QSpinBox, QCheckBox
)
from themes.dark_theme import ACCENT_COLOR, TEXT_COLOR, SUB_COLOR, BG_COLOR


# ─────────────────────────────────────────────────────────────
# Worker thread che pinga un host
# ─────────────────────────────────────────────────────────────
class PingWorker(QThread):
    result = pyqtSignal(str, bool, float)   # host, reachable, latency_ms

    def __init__(self, host: str, port: int = 22, timeout: float = 1.5):
        super().__init__()
        self.host    = host
        self.port    = port
        self.timeout = timeout

    def run(self):
        import time
        try:
            start = time.monotonic()
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.timeout)
            r = s.connect_ex((self.host, self.port))
            s.close()
            elapsed = (time.monotonic() - start) * 1000
            self.result.emit(self.host, r == 0, round(elapsed, 1))
        except Exception:
            self.result.emit(self.host, False, -1.0)


# ─────────────────────────────────────────────────────────────
# Pannello
# ─────────────────────────────────────────────────────────────
class PingMonitorPanel(QWidget):
    connection_open_requested = pyqtSignal(str)   # hostname

    _STATUS_UP   = "#4EC94E"
    _STATUS_DOWN = "#EF5350"
    _STATUS_UNKN = "#555555"

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hosts: List[dict] = []     # {host, port, name, status, latency, worker}
        self._timer  = QTimer(self)
        self._timer.timeout.connect(self._refresh_all)
        self._setup_ui()

    # ── UI ──

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Ping Monitor")
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{TEXT_COLOR}; background:transparent;")
        hdr.addWidget(title)
        hdr.addStretch()

        interval_lbl = QLabel("Intervallo (s):")
        interval_lbl.setStyleSheet(f"color:{SUB_COLOR}; background:transparent; font-size:11px;")
        hdr.addWidget(interval_lbl)

        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(5, 300)
        self._interval_spin.setValue(30)
        self._interval_spin.setFixedWidth(60)
        self._interval_spin.setStyleSheet(
            f"background:#1E1E1E; color:{TEXT_COLOR}; border:1px solid #333; border-radius:3px;")
        hdr.addWidget(self._interval_spin)

        self._auto_cb = QCheckBox("Auto")
        self._auto_cb.setStyleSheet(f"color:{SUB_COLOR}; background:transparent; font-size:11px;")
        self._auto_cb.stateChanged.connect(self._on_auto_toggle)
        hdr.addWidget(self._auto_cb)

        self._refresh_btn = QPushButton("Aggiorna ora")
        self._refresh_btn.setFixedHeight(24)
        self._refresh_btn.setStyleSheet(f"""
            QPushButton {{ background:{ACCENT_COLOR}; color:white; border:none;
                          border-radius:3px; padding:0 10px; font-size:11px; }}
            QPushButton:hover {{ background:#0088DD; }}
        """)
        self._refresh_btn.clicked.connect(self._refresh_all)
        hdr.addWidget(self._refresh_btn)
        layout.addLayout(hdr)

        # Tabella
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["Stato", "Nome", "Host", "Porta", "Latenza"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(0, 60)
        self._table.setColumnWidth(3, 60)
        self._table.setColumnWidth(4, 80)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background:{BG_COLOR}; color:{TEXT_COLOR};
                border:1px solid #2A2A2A; border-radius:3px;
                alternate-background-color:#111111; gridline-color:#1A1A1A;
            }}
            QHeaderView::section {{
                background:#1A1A1A; color:{SUB_COLOR};
                border:none; border-right:1px solid #2A2A2A;
                padding:4px 8px; font-size:11px;
            }}
            QTableWidget::item:selected {{ background:#1A3A5A; color:white; }}
        """)
        layout.addWidget(self._table)

        # Stats bar
        self._stats_lbl = QLabel("Nessun host monitorato")
        self._stats_lbl.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px; background:transparent;")
        layout.addWidget(self._stats_lbl)

    # ── API pubblica ──

    def set_hosts(self, connections: list):
        """Popola il monitor con la lista di ConnectionInfo."""
        self._hosts.clear()
        self._table.setRowCount(0)
        for conn in connections:
            if not conn.hostname:
                continue
            port = conn.port or conn.get_default_port() or 22
            entry = {
                "host": conn.hostname, "port": port,
                "name": conn.name, "status": None,
                "latency": -1.0, "worker": None,
            }
            self._hosts.append(entry)
            self._add_table_row(entry)
        self._update_stats()

    # ── Internals ──

    def _add_table_row(self, entry: dict):
        row = self._table.rowCount()
        self._table.insertRow(row)
        for col in range(5):
            item = QTableWidgetItem()
            item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self._table.setItem(row, col, item)
        self._table.item(row, 1).setText(entry["name"])
        self._table.item(row, 2).setText(entry["host"])
        self._table.item(row, 3).setText(str(entry["port"]))
        self._set_row_status(row, None, -1.0)

    def _set_row_status(self, row: int, up: Optional[bool], latency: float):
        if up is None:
            dot, color, lat_txt = "●", self._STATUS_UNKN, "—"
        elif up:
            dot, color = "●", self._STATUS_UP
            lat_txt = f"{latency:.0f} ms" if latency >= 0 else "—"
        else:
            dot, color, lat_txt = "●", self._STATUS_DOWN, "timeout"

        status_item = self._table.item(row, 0)
        if status_item:
            status_item.setText(dot)
            status_item.setForeground(QColor(color))
            status_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

        lat_item = self._table.item(row, 4)
        if lat_item:
            lat_item.setText(lat_txt)
            lat_item.setForeground(QColor(color))

    def _refresh_all(self):
        for i, entry in enumerate(self._hosts):
            if entry.get("worker") and entry["worker"].isRunning():
                continue
            w = PingWorker(entry["host"], entry["port"])
            entry["worker"] = w
            row = i
            w.result.connect(lambda h, up, lat, r=row, e=entry:
                             self._on_ping_result(r, e, up, lat))
            w.start()

    def _on_ping_result(self, row: int, entry: dict, up: bool, latency: float):
        prev = entry.get("status")
        entry["status"]  = up
        entry["latency"] = latency
        self._set_row_status(row, up, latency)
        self._update_stats()

        # Log alert se host passa da UP a DOWN
        if prev is True and not up:
            try:
                from core.session_logger import SessionLogger
                SessionLogger.get_instance().log(
                    "ERROR", entry["host"], "PING",
                    f"Host non raggiungibile su porta {entry['port']}"
                )
            except Exception:
                pass

    def _update_stats(self):
        total = len(self._hosts)
        if total == 0:
            self._stats_lbl.setText("Nessun host monitorato")
            return
        up   = sum(1 for e in self._hosts if e["status"] is True)
        down = sum(1 for e in self._hosts if e["status"] is False)
        unkn = total - up - down
        self._stats_lbl.setText(
            f"<span style='color:#4EC94E'>● {up} UP</span>  "
            f"<span style='color:#EF5350'>● {down} DOWN</span>  "
            f"<span style='color:#555'>● {unkn} sconosciuti</span>  "
            f"— {total} host totali"
        )

    def _on_auto_toggle(self, state: int):
        if state == Qt.CheckState.Checked.value:
            interval_ms = self._interval_spin.value() * 1000
            self._timer.start(interval_ms)
        else:
            self._timer.stop()
