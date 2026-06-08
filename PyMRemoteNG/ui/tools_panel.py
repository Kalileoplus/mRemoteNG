"""
Pannello Tools: Port Scanner, Ping Monitor, Network Discovery.
"""
from __future__ import annotations
import socket
from typing import Dict, List, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QTextEdit, QProgressBar, QTabWidget,
    QTableWidget, QTableWidgetItem, QHeaderView, QCheckBox
)
from themes.dark_theme import ACCENT_COLOR, TEXT_COLOR, SUB_COLOR, BG_COLOR, CARD_COLOR

# ─────────────────────────────────────────────────────────────
# Port Scanner thread
# ─────────────────────────────────────────────────────────────
class PortScanThread(QThread):
    port_open = pyqtSignal(int, str)   # port, service  — solo porte aperte
    scan_progress = pyqtSignal(int)    # N porte scansionate
    scan_done = pyqtSignal(int)        # N porte aperte totali

    COMMON_PORTS = {
        21:"FTP", 22:"SSH", 23:"Telnet", 25:"SMTP", 53:"DNS",
        80:"HTTP", 110:"POP3", 143:"IMAP", 443:"HTTPS",
        445:"SMB", 993:"IMAPS", 995:"POP3S", 1433:"MSSQL",
        1521:"Oracle", 3306:"MySQL", 3389:"RDP", 5432:"PostgreSQL",
        5900:"VNC", 6379:"Redis", 8080:"HTTP-Alt", 8443:"HTTPS-Alt",
        9200:"Elasticsearch", 27017:"MongoDB",
    }

    def __init__(self, host: str, port_start: int, port_end: int, timeout: float = 0.5):
        super().__init__()
        self.host       = host
        self.port_start = port_start   # NON chiamare self.start: sovrascrive QThread.start()
        self.port_end   = port_end
        self.timeout    = timeout
        self._stop      = False

    def run(self):
        open_count = 0
        ports = list(range(self.port_start, self.port_end + 1))
        for i, port in enumerate(ports):
            if self._stop:
                break
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(self.timeout)
                if s.connect_ex((self.host, port)) == 0:
                    open_count += 1
                    self.port_open.emit(port, self.COMMON_PORTS.get(port, ""))
                s.close()
            except Exception:
                pass
            if i % 5 == 0 or i == len(ports) - 1:
                self.scan_progress.emit(i + 1)
        self.scan_done.emit(open_count)

    def stop(self):
        self._stop = True


# ─────────────────────────────────────────────────────────────
# Port Scanner widget
# ─────────────────────────────────────────────────────────────
_STYLE_INPUT = (
    f"background:#141414; color:{TEXT_COLOR}; "
    f"border:1px solid #2A2A2A; border-radius:4px; padding:4px 8px; font-size:12px;"
)
_STYLE_INPUT_FOCUS = (
    f"background:#141414; color:{TEXT_COLOR}; "
    f"border:1px solid {ACCENT_COLOR}; border-radius:4px; padding:4px 8px; font-size:12px;"
)


class PortScannerWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._scan_thread: Optional[PortScanThread] = None
        self._setup_ui()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        # Header
        hdr = QLabel("Port Scanner")
        hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color:{ACCENT_COLOR}; background:transparent;")
        lay.addWidget(hdr)

        sub = QLabel("Scansiona le porte aperte su un host di rete")
        sub.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px; background:transparent;")
        lay.addWidget(sub)

        # Host
        row_host = QHBoxLayout()
        lh = QLabel("Host / IP:")
        lh.setFixedWidth(80)
        lh.setStyleSheet(f"color:{SUB_COLOR}; background:transparent;")
        self._host_edit = QLineEdit()
        self._host_edit.setPlaceholderText("es. 192.168.1.1 oppure server01")
        self._host_edit.setStyleSheet(_STYLE_INPUT)
        self._host_edit.returnPressed.connect(self._start_scan)
        row_host.addWidget(lh)
        row_host.addWidget(self._host_edit)
        lay.addLayout(row_host)

        # Range porte
        row_ports = QHBoxLayout()
        lp1 = QLabel("Da porta:")
        lp1.setFixedWidth(80)
        lp1.setStyleSheet(f"color:{SUB_COLOR}; background:transparent;")
        self._port_from = QSpinBox()
        self._port_from.setRange(1, 65535)
        self._port_from.setValue(1)
        self._port_from.setFixedWidth(75)
        self._port_from.setStyleSheet(_STYLE_INPUT)

        lp2 = QLabel("a:")
        lp2.setStyleSheet(f"color:{SUB_COLOR}; background:transparent; margin:0 4px;")
        self._port_to = QSpinBox()
        self._port_to.setRange(1, 65535)
        self._port_to.setValue(1024)
        self._port_to.setFixedWidth(75)
        self._port_to.setStyleSheet(_STYLE_INPUT)

        row_ports.addWidget(lp1)
        row_ports.addWidget(self._port_from)
        row_ports.addWidget(lp2)
        row_ports.addWidget(self._port_to)
        row_ports.addStretch()
        lay.addLayout(row_ports)

        # Timeout
        row_to = QHBoxLayout()
        lt = QLabel("Timeout (s):")
        lt.setFixedWidth(80)
        lt.setStyleSheet(f"color:{SUB_COLOR}; background:transparent;")
        self._timeout_spin = QSpinBox()
        self._timeout_spin.setRange(1, 30)
        self._timeout_spin.setValue(1)
        self._timeout_spin.setFixedWidth(55)
        self._timeout_spin.setStyleSheet(_STYLE_INPUT)
        row_to.addWidget(lt)
        row_to.addWidget(self._timeout_spin)
        row_to.addStretch()
        lay.addLayout(row_to)

        # Bottoni
        btn_row = QHBoxLayout()
        self._scan_btn = QPushButton("▶  Avvia scansione")
        self._scan_btn.setFixedHeight(32)
        self._scan_btn.setStyleSheet(f"""
            QPushButton {{ background:{ACCENT_COLOR}; color:white; border:none;
                          border-radius:4px; padding:0 16px; font-weight:bold; font-size:12px; }}
            QPushButton:hover {{ background:#0088DD; }}
            QPushButton:disabled {{ background:#1E1E1E; color:#444; }}
        """)
        self._scan_btn.clicked.connect(self._start_scan)
        btn_row.addWidget(self._scan_btn)

        self._stop_btn = QPushButton("⏹  Stop")
        self._stop_btn.setEnabled(False)
        self._stop_btn.setFixedHeight(32)
        self._stop_btn.setStyleSheet(f"""
            QPushButton {{ background:#1E1E1E; color:{TEXT_COLOR}; border:1px solid #333;
                          border-radius:4px; padding:0 14px; font-size:12px; }}
            QPushButton:hover {{ background:#2A2A2A; }}
            QPushButton:disabled {{ color:#444; border-color:#222; }}
        """)
        self._stop_btn.clicked.connect(self._stop_scan)
        btn_row.addWidget(self._stop_btn)
        btn_row.addStretch()
        lay.addLayout(btn_row)

        # Progress bar
        self._pbar = QProgressBar()
        self._pbar.setVisible(False)
        self._pbar.setFixedHeight(6)
        self._pbar.setTextVisible(False)
        self._pbar.setStyleSheet(f"""
            QProgressBar {{ background:#1A1A1A; border:none; border-radius:3px; }}
            QProgressBar::chunk {{ background:{ACCENT_COLOR}; border-radius:3px; }}
        """)
        lay.addWidget(self._pbar)

        # Output
        self._output = QTextEdit()
        self._output.setReadOnly(True)
        self._output.setFont(QFont("Cascadia Code,Consolas,Courier New", 11))
        self._output.setStyleSheet(f"""
            QTextEdit {{ background:#0A0A0A; color:#D4D4D4;
                        border:1px solid #1E1E1E; border-radius:4px; padding:6px; }}
        """)
        lay.addWidget(self._output)

    def _start_scan(self):
        host = self._host_edit.text().strip()
        if not host:
            self._host_edit.setStyleSheet(_STYLE_INPUT_FOCUS)
            self._host_edit.setFocus()
            return
        self._host_edit.setStyleSheet(_STYLE_INPUT)

        pf = self._port_from.value()
        pt = self._port_to.value()
        if pf > pt:
            pf, pt = pt, pf

        self._output.clear()
        self._output.append(
            f'<span style="color:{SUB_COLOR}">Scanning {host}  porte {pf}–{pt}...</span><br>'
        )

        total = pt - pf + 1
        self._pbar.setRange(0, total)
        self._pbar.setValue(0)
        self._pbar.setVisible(True)
        self._scan_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)

        self._scan_thread = PortScanThread(host, pf, pt, float(self._timeout_spin.value()))
        self._scan_thread.port_open.connect(self._on_port_open)
        self._scan_thread.scan_progress.connect(self._pbar.setValue)
        self._scan_thread.scan_done.connect(self._on_scan_done)
        self._scan_thread.start()

    def _on_port_open(self, port: int, service: str):
        badge = f' <span style="color:#888; font-size:10px">({service})</span>' if service else ""
        self._output.append(
            f'<span style="color:#4EC94E">● {port}/tcp  OPEN</span>{badge}'
        )

    def _on_scan_done(self, open_count: int):
        self._pbar.setVisible(False)
        self._scan_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._output.append(
            f'<br><span style="color:{SUB_COLOR}">─── Completata: '
            f'<b style="color:{TEXT_COLOR}">{open_count}</b> porte aperte ───</span>'
        )

    def _stop_scan(self):
        if self._scan_thread:
            self._scan_thread.stop()
        self._pbar.setVisible(False)
        self._scan_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

    def closeEvent(self, event):
        if self._scan_thread and self._scan_thread.isRunning():
            self._scan_thread.stop()
            self._scan_thread.quit()
        super().closeEvent(event)


# ─────────────────────────────────────────────────────────────
# Ping Monitor widget
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
            ms = (time.monotonic() - start) * 1000
            self.result.emit(self.host, r == 0, round(ms, 1))
        except Exception:
            self.result.emit(self.host, False, -1.0)


class PingMonitorPanel(QWidget):
    connection_open_requested = pyqtSignal(str)
    host_down = pyqtSignal(str, int)   # hostname, porta — emesso quando UP→DOWN

    def __init__(self, parent=None):
        super().__init__(parent)
        self._entries: List[Dict] = []
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh_all)
        self._setup_ui()

    def _setup_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        # Header
        hdr = QLabel("Ping Monitor")
        hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color:{ACCENT_COLOR}; background:transparent;")
        lay.addWidget(hdr)

        # Aggiungi IP manuale
        add_row = QHBoxLayout()
        self._ip_edit = QLineEdit()
        self._ip_edit.setPlaceholderText("Aggiungi IP o hostname  (es. 192.168.1.1)")
        self._ip_edit.setStyleSheet(_STYLE_INPUT)
        self._ip_edit.setFixedHeight(30)
        self._ip_edit.returnPressed.connect(self._add_custom_host)
        add_row.addWidget(self._ip_edit)

        add_btn = QPushButton("+ Aggiungi")
        add_btn.setFixedHeight(30)
        add_btn.setStyleSheet(f"""
            QPushButton {{ background:{ACCENT_COLOR}; color:white; border:none;
                          border-radius:4px; padding:0 12px; font-size:11px; }}
            QPushButton:hover {{ background:#0088DD; }}
        """)
        add_btn.clicked.connect(self._add_custom_host)
        add_row.addWidget(add_btn)

        rem_btn = QPushButton("Rimuovi")
        rem_btn.setFixedHeight(30)
        rem_btn.setStyleSheet(f"""
            QPushButton {{ background:#1E1E1E; color:{TEXT_COLOR}; border:1px solid #333;
                          border-radius:4px; padding:0 10px; font-size:11px; }}
            QPushButton:hover {{ background:#2A2A2A; }}
        """)
        rem_btn.clicked.connect(self._remove_selected)
        add_row.addWidget(rem_btn)
        lay.addLayout(add_row)

        # Controlli auto-refresh
        ctrl_row = QHBoxLayout()
        self._auto_cb = QCheckBox("Auto-refresh ogni")
        self._auto_cb.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px; background:transparent;")
        self._auto_cb.stateChanged.connect(self._on_auto_toggle)
        ctrl_row.addWidget(self._auto_cb)

        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(5, 300)
        self._interval_spin.setValue(30)
        self._interval_spin.setFixedWidth(55)
        self._interval_spin.setStyleSheet(_STYLE_INPUT)
        ctrl_row.addWidget(self._interval_spin)

        ctrl_row.addWidget(QLabel("s"))
        ctrl_row.addStretch()

        ping_btn = QPushButton("Ping ora")
        ping_btn.setFixedHeight(28)
        ping_btn.setStyleSheet(f"""
            QPushButton {{ background:#1E1E1E; color:{TEXT_COLOR}; border:1px solid #333;
                          border-radius:4px; padding:0 12px; font-size:11px; }}
            QPushButton:hover {{ background:{ACCENT_COLOR}; color:white; border-color:{ACCENT_COLOR}; }}
        """)
        ping_btn.clicked.connect(self._refresh_all)
        ctrl_row.addWidget(ping_btn)
        lay.addLayout(ctrl_row)

        # Fix label color nel ctrl_row
        for i in range(ctrl_row.count()):
            item = ctrl_row.itemAt(i)
            if item and isinstance(item.widget(), QLabel):
                item.widget().setStyleSheet(f"color:{SUB_COLOR}; background:transparent; font-size:11px;")

        # Tabella
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Stato", "Host / Nome", "Porta", "Latenza"])
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(0, 56)
        self._table.setColumnWidth(2, 60)
        self._table.setColumnWidth(3, 80)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background:{BG_COLOR}; color:{TEXT_COLOR};
                border:1px solid #1E1E1E; border-radius:4px;
                alternate-background-color:#0D0D0D;
            }}
            QHeaderView::section {{
                background:#141414; color:{SUB_COLOR};
                border:none; border-bottom:1px solid #1E1E1E;
                padding:5px 8px; font-size:11px;
            }}
            QTableWidget::item:selected {{ background:#1A3A5A; color:white; }}
        """)
        lay.addWidget(self._table)

        # Stats
        self._stats_lbl = QLabel("Nessun host monitorato")
        self._stats_lbl.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px; background:transparent;")
        lay.addWidget(self._stats_lbl)

    def _add_custom_host(self):
        text = self._ip_edit.text().strip()
        if not text:
            return
        # Supporta formato "host:porta"
        port = 22
        if ":" in text:
            parts = text.rsplit(":", 1)
            try:
                port = int(parts[1])
                text = parts[0]
            except ValueError:
                pass
        # Evita duplicati
        for e in self._entries:
            if e["host"] == text and e["port"] == port:
                self._ip_edit.clear()
                return
        entry = {"host": text, "port": port, "name": text,
                 "status": None, "latency": -1.0, "worker": None}
        self._entries.append(entry)
        self._add_table_row(entry)
        self._ip_edit.clear()
        self._update_stats()

    def _remove_selected(self):
        rows = sorted({i.row() for i in self._table.selectedItems()}, reverse=True)
        for row in rows:
            if row < len(self._entries):
                self._entries.pop(row)
                self._table.removeRow(row)
        self._update_stats()

    def set_hosts(self, connections: list):
        """Aggiunge le connessioni dalla connection tree (non sovrascrive host manuali)."""
        existing = {(e["host"], e["port"]) for e in self._entries}
        for conn in connections:
            if not conn.hostname:
                continue
            port = conn.port or conn.get_default_port() or 22
            key = (conn.hostname, port)
            if key in existing:
                continue
            entry = {"host": conn.hostname, "port": port, "name": conn.name,
                     "status": None, "latency": -1.0, "worker": None}
            self._entries.append(entry)
            existing.add(key)
            self._add_table_row(entry)
        self._update_stats()

    def _add_table_row(self, entry: Dict):
        row = self._table.rowCount()
        self._table.insertRow(row)
        for col in range(4):
            item = QTableWidgetItem()
            item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            self._table.setItem(row, col, item)
        self._table.item(row, 1).setText(
            f"{entry['name']}" + (f"\n{entry['host']}" if entry['name'] != entry['host'] else "")
        )
        self._table.item(row, 2).setText(str(entry["port"]))
        self._table.setRowHeight(row, 36)
        self._set_row_status(row, None, -1.0)

    def _set_row_status(self, row: int, up: Optional[bool], lat: float):
        if up is None:
            dot, color, lat_txt = "●", "#3A3A3A", "—"
        elif up:
            dot, color = "●", "#4EC94E"
            lat_txt = f"{lat:.0f} ms" if lat >= 0 else "—"
        else:
            dot, color, lat_txt = "●", "#EF5350", "timeout"

        s = self._table.item(row, 0)
        if s:
            s.setText(dot)
            s.setForeground(QColor(color))
            s.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        l = self._table.item(row, 3)
        if l:
            l.setText(lat_txt)
            l.setForeground(QColor(color))

    def _refresh_all(self):
        for i, entry in enumerate(self._entries):
            w = entry.get("worker")
            if w and w.isRunning():
                continue
            worker = PingWorker(entry["host"], entry["port"])
            entry["worker"] = worker
            row = i
            worker.result.connect(
                lambda h, up, lat, r=row, e=entry: self._on_ping(r, e, up, lat)
            )
            worker.start()

    def _on_ping(self, row: int, entry: Dict, up: bool, lat: float):
        prev = entry.get("status")
        entry["status"] = up
        entry["latency"] = lat
        self._set_row_status(row, up, lat)
        self._update_stats()
        if prev is True and not up:
            self.host_down.emit(entry["host"], entry["port"])
            try:
                from core.session_logger import SessionLogger
                SessionLogger.get_instance().log(
                    "ERROR", entry["host"], "PING",
                    f"Host non raggiungibile porta {entry['port']}"
                )
            except Exception:
                pass

    def _update_stats(self):
        total = len(self._entries)
        if total == 0:
            self._stats_lbl.setText("Nessun host monitorato")
            return
        up   = sum(1 for e in self._entries if e["status"] is True)
        down = sum(1 for e in self._entries if e["status"] is False)
        self._stats_lbl.setText(
            f"<span style='color:#4EC94E'>● {up} UP</span>  "
            f"<span style='color:#EF5350'>● {down} DOWN</span>  "
            f"<span style='color:#555'>● {total - up - down} sconosciuti</span>"
            f"  —  {total} host"
        )

    def _on_auto_toggle(self, state: int):
        if state == Qt.CheckState.Checked.value:
            self._timer.start(self._interval_spin.value() * 1000)
        else:
            self._timer.stop()


# ─────────────────────────────────────────────────────────────
# Tools Panel con tab
# ─────────────────────────────────────────────────────────────
class ToolsPanel(QWidget):
    hosts_discovered = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:{BG_COLOR};")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        tabs = QTabWidget()
        tabs.setStyleSheet(f"""
            QTabWidget::pane  {{ background:{BG_COLOR}; border:none; }}
            QTabBar::tab {{
                background:#141414; color:{SUB_COLOR};
                padding:6px 16px; border:none;
                border-right:1px solid #1E1E1E; font-size:11px;
            }}
            QTabBar::tab:selected {{ background:{BG_COLOR}; color:{TEXT_COLOR};
                                     border-top:2px solid {ACCENT_COLOR}; }}
            QTabBar::tab:hover    {{ background:#1A1A1A; color:{TEXT_COLOR}; }}
        """)

        tabs.addTab(PortScannerWidget(), "Port Scanner")

        self.ping_monitor = PingMonitorPanel()
        tabs.addTab(self.ping_monitor, "Ping Monitor")

        disc_widget = self._make_discovery_launcher()
        tabs.addTab(disc_widget, "Network Discovery")

        lay.addWidget(tabs)

    def _make_discovery_launcher(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:{BG_COLOR};")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(20, 24, 20, 20)
        lay.setSpacing(12)

        title = QLabel("Network Discovery")
        title.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{ACCENT_COLOR};")
        lay.addWidget(title)

        desc = QLabel(
            "Scansiona la rete per trovare host attivi su una subnet CIDR.\n"
            "Puoi aggiungere gli host scoperti direttamente alle connessioni."
        )
        desc.setWordWrap(True)
        desc.setStyleSheet(f"color:{SUB_COLOR}; font-size:12px;")
        lay.addWidget(desc)

        btn = QPushButton("Avvia Network Discovery…")
        btn.setFixedHeight(38)
        btn.setStyleSheet(f"""
            QPushButton {{ background:{ACCENT_COLOR}; color:white; border:none;
                          border-radius:4px; font-size:13px; font-weight:bold; }}
            QPushButton:hover {{ background:#0088DD; }}
        """)
        btn.clicked.connect(self._open_discovery)
        lay.addWidget(btn)
        lay.addStretch()
        return w

    def _open_discovery(self):
        from ui.dialogs.network_discovery_dialog import NetworkDiscoveryDialog
        dlg = NetworkDiscoveryDialog(parent=self)
        dlg.hosts_to_add.connect(self.hosts_discovered)
        dlg.exec()

    def set_connections(self, connections: list):
        self.ping_monitor.set_hosts(connections)
