"""
Pannello Tools (tab verticale sinistra) — Port Scanner, SSH Keygen, ecc.
"""
import socket, threading
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QSpinBox, QTextEdit, QProgressBar, QFrame
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont
from themes.dark_theme import ACCENT_COLOR, CARD_COLOR, TEXT_COLOR, SUB_COLOR, BG_COLOR


class PortScanThread(QThread):
    result  = pyqtSignal(int, bool, str)   # port, open, service
    done    = pyqtSignal(int)              # open_count

    COMMON_PORTS = {
        21:"FTP", 22:"SSH", 23:"Telnet", 25:"SMTP", 53:"DNS",
        80:"HTTP", 110:"POP3", 143:"IMAP", 443:"HTTPS",
        445:"SMB", 993:"IMAPS", 995:"POP3S", 1433:"MSSQL",
        1521:"Oracle", 3306:"MySQL", 3389:"RDP", 5432:"PostgreSQL",
        5900:"VNC", 6379:"Redis", 8080:"HTTP-Alt", 8443:"HTTPS-Alt",
        9200:"Elasticsearch", 27017:"MongoDB",
    }

    def __init__(self, host: str, start: int, end: int, timeout: float = 0.5):
        super().__init__()
        self.host = host; self.start = start; self.end = end
        self.timeout = timeout; self._stop = False

    def run(self):
        open_count = 0
        for port in range(self.start, self.end + 1):
            if self._stop: break
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(self.timeout)
                r = s.connect_ex((self.host, port))
                s.close()
                is_open = (r == 0)
                if is_open: open_count += 1
                service = self.COMMON_PORTS.get(port, "")
                self.result.emit(port, is_open, service)
            except Exception:
                self.result.emit(port, False, "")
        self.done.emit(open_count)

    def stop(self):
        self._stop = True


class PortScannerWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._thread: PortScanThread | None = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        title = QLabel("🔍  Port Scanner")
        title.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{TEXT_COLOR}; background:transparent;")
        layout.addWidget(title)

        # Host
        row1 = QHBoxLayout()
        lbl = QLabel("Host:"); lbl.setFixedWidth(50)
        lbl.setStyleSheet(f"color:{SUB_COLOR}; background:transparent;")
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("172.16.0.1")
        self.host_input.setStyleSheet(f"background:#1E1E1E; color:{TEXT_COLOR}; border:1px solid #333; border-radius:3px; padding:3px 6px;")
        row1.addWidget(lbl); row1.addWidget(self.host_input)
        layout.addLayout(row1)

        # Range porte
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Porta da:"))
        self.port_from = QSpinBox(); self.port_from.setRange(1,65535); self.port_from.setValue(1)
        self.port_from.setStyleSheet(f"background:#1E1E1E; color:{TEXT_COLOR}; border:1px solid #333; border-radius:3px;")
        row2.addWidget(self.port_from)
        row2.addWidget(QLabel("a:"))
        self.port_to = QSpinBox(); self.port_to.setRange(1,65535); self.port_to.setValue(1024)
        self.port_to.setStyleSheet(f"background:#1E1E1E; color:{TEXT_COLOR}; border:1px solid #333; border-radius:3px;")
        for lbl in row2.children() if False else []:  # fix label styles
            pass
        for w in [self.port_from, self.port_to]:
            w.setFixedWidth(70)
        # Fix label colors
        for i in range(row2.count()):
            item = row2.itemAt(i)
            if item and item.widget() and isinstance(item.widget(), QLabel):
                item.widget().setStyleSheet(f"color:{SUB_COLOR}; background:transparent;")
        row2.addWidget(self.port_to)
        layout.addLayout(row2)

        # Bottoni
        btn_row = QHBoxLayout()
        self.scan_btn = QPushButton("▶ Scansiona")
        self.scan_btn.setStyleSheet(f"""
            QPushButton {{ background:{ACCENT_COLOR}; color:white; border:none; border-radius:3px;
                padding:4px 12px; font-weight:bold; }}
            QPushButton:hover {{ background:#0088DD; }}
        """)
        self.scan_btn.clicked.connect(self._start_scan)
        btn_row.addWidget(self.scan_btn)

        self.stop_btn = QPushButton("⏹ Stop")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet(f"background:#2A2A2A; color:{TEXT_COLOR}; border:1px solid #333; border-radius:3px; padding:4px 10px;")
        self.stop_btn.clicked.connect(self._stop_scan)
        btn_row.addWidget(self.stop_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        self.progress = QProgressBar()
        self.progress.setVisible(False)
        self.progress.setStyleSheet(f"""
            QProgressBar {{ background:#1E1E1E; border:1px solid #333; border-radius:3px; height:8px; }}
            QProgressBar::chunk {{ background:{ACCENT_COLOR}; border-radius:3px; }}
        """)
        layout.addWidget(self.progress)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(QFont("Consolas", 10))
        self.output.setStyleSheet(f"background:#0C0C0C; color:#D4D4D4; border:1px solid #2A2A2A; border-radius:3px;")
        layout.addWidget(self.output)

    def _start_scan(self):
        host  = self.host_input.text().strip()
        if not host: return
        pf, pt = self.port_from.value(), self.port_to.value()
        self.output.clear()
        self.output.append(f"Scanning {host}:{pf}-{pt}...\n")
        total = pt - pf + 1
        self.progress.setRange(0, total); self.progress.setValue(0)
        self.progress.setVisible(True)
        self.scan_btn.setEnabled(False); self.stop_btn.setEnabled(True)
        self._scanned = 0
        self._thread = PortScanThread(host, pf, pt)
        self._thread.result.connect(self._on_result)
        self._thread.done.connect(self._on_done)
        self._thread.start()

    def _on_result(self, port: int, is_open: bool, service: str):
        self._scanned += 1
        self.progress.setValue(self._scanned)
        if is_open:
            svc = f"  ({service})" if service else ""
            self.output.append(f"<span style='color:#4EC94E'>✓  {port}/tcp  OPEN{svc}</span>")

    def _on_done(self, open_count: int):
        self.output.append(f"\n<span style='color:#888'>Completato. {open_count} porte aperte.</span>")
        self.progress.setVisible(False)
        self.scan_btn.setEnabled(True); self.stop_btn.setEnabled(False)

    def _stop_scan(self):
        if self._thread: self._thread.stop()
        self.scan_btn.setEnabled(True); self.stop_btn.setEnabled(False)
        self.progress.setVisible(False)


class ToolsPanel(QWidget):
    """Pannello Tools con port scanner e altri strumenti."""
    def __init__(self):
        super().__init__()
        self.setStyleSheet(f"background:#111111;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QLabel("  🔧  Tools")
        header.setFixedHeight(32)
        header.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        header.setStyleSheet(f"background:#1A1A1A; color:{SUB_COLOR}; border-bottom:1px solid #2A2A2A; padding-left:6px;")
        layout.addWidget(header)

        layout.addWidget(PortScannerWidget())
