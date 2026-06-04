"""
Network Discovery Dialog: ping sweep + port scan su subnet.
Permette di aggiungere gli host trovati direttamente alle connessioni.
"""
from __future__ import annotations
import ipaddress
import socket
import threading
from typing import List, Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QProgressBar, QCheckBox, QComboBox, QWidget, QMessageBox
)
from themes.dark_theme import ACCENT_COLOR, TEXT_COLOR, SUB_COLOR, BG_COLOR, CARD_COLOR


COMMON_PORTS = {22: "SSH", 23: "Telnet", 80: "HTTP", 443: "HTTPS",
                3389: "RDP", 5900: "VNC", 8080: "HTTP-Alt"}


class DiscoveryWorker(QThread):
    host_found  = pyqtSignal(str, int, str)   # ip, port, service
    progress    = pyqtSignal(int)             # scanned count
    done        = pyqtSignal()

    def __init__(self, subnet: str, ports: List[int], timeout: float = 0.4):
        super().__init__()
        self.subnet  = subnet
        self.ports   = ports
        self.timeout = timeout
        self._stop   = False

    def run(self):
        try:
            net = ipaddress.ip_network(self.subnet, strict=False)
        except ValueError:
            self.done.emit()
            return

        hosts = list(net.hosts())
        total = len(hosts)

        for i, ip in enumerate(hosts):
            if self._stop:
                break
            ip_str = str(ip)
            for port in self.ports:
                if self._stop:
                    break
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(self.timeout)
                    if s.connect_ex((ip_str, port)) == 0:
                        service = COMMON_PORTS.get(port, str(port))
                        self.host_found.emit(ip_str, port, service)
                    s.close()
                except Exception:
                    pass
            if i % 5 == 0:
                self.progress.emit(i + 1)

        self.progress.emit(total)
        self.done.emit()

    def stop(self):
        self._stop = True


class NetworkDiscoveryDialog(QDialog):
    hosts_to_add = pyqtSignal(list)   # list of dict {ip, port, service}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Network Discovery")
        self.setMinimumSize(680, 520)
        self._worker: Optional[DiscoveryWorker] = None
        self._found: List[dict] = []
        self._setup_ui()
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet(f"""
            QDialog {{ background:{BG_COLOR}; color:{TEXT_COLOR}; }}
            QLabel  {{ background:transparent; color:{TEXT_COLOR}; }}
            QLineEdit, QComboBox {{
                background:#1E1E1E; color:{TEXT_COLOR};
                border:1px solid #333; border-radius:3px; padding:4px 8px;
            }}
            QLineEdit:focus, QComboBox:focus {{ border-color:{ACCENT_COLOR}; }}
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        # Titolo
        title = QLabel("Scansione Rete")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{ACCENT_COLOR};")
        layout.addWidget(title)

        # Input riga
        row = QHBoxLayout()
        subnet_lbl = QLabel("Subnet (CIDR):")
        subnet_lbl.setFixedWidth(120)
        self._subnet_input = QLineEdit()
        self._subnet_input.setPlaceholderText("192.168.1.0/24")
        self._subnet_input.setText("192.168.1.0/24")
        row.addWidget(subnet_lbl)
        row.addWidget(self._subnet_input)

        proto_lbl = QLabel("Cerca:")
        proto_lbl.setFixedWidth(50)
        self._proto_combo = QComboBox()
        self._proto_combo.addItems(["SSH (22)", "RDP (3389)", "Tutti i comuni", "Personalizzato"])
        self._proto_combo.setFixedWidth(150)
        row.addWidget(proto_lbl)
        row.addWidget(self._proto_combo)
        layout.addLayout(row)

        # Porte personalizzate
        self._custom_ports_row = QWidget()
        custom_layout = QHBoxLayout(self._custom_ports_row)
        custom_layout.setContentsMargins(0, 0, 0, 0)
        custom_lbl = QLabel("Porte (es. 22,80,443):")
        custom_lbl.setFixedWidth(160)
        self._custom_ports_input = QLineEdit()
        self._custom_ports_input.setPlaceholderText("22,80,443,3389")
        custom_layout.addWidget(custom_lbl)
        custom_layout.addWidget(self._custom_ports_input)
        self._custom_ports_row.setVisible(False)
        layout.addWidget(self._custom_ports_row)
        self._proto_combo.currentIndexChanged.connect(
            lambda i: self._custom_ports_row.setVisible(i == 3)
        )

        # Bottoni
        btn_row = QHBoxLayout()
        self._scan_btn = QPushButton("Avvia scansione")
        self._scan_btn.setStyleSheet(f"""
            QPushButton {{ background:{ACCENT_COLOR}; color:white; border:none;
                          border-radius:4px; padding:6px 16px; font-weight:bold; }}
            QPushButton:hover {{ background:#0088DD; }}
            QPushButton:disabled {{ background:#333; color:#666; }}
        """)
        self._scan_btn.clicked.connect(self._start_scan)
        btn_row.addWidget(self._scan_btn)

        self._stop_btn = QPushButton("Stop")
        self._stop_btn.setEnabled(False)
        self._stop_btn.setStyleSheet(
            f"QPushButton {{ background:#2A2A2A; color:{TEXT_COLOR}; border:1px solid #444;"
            f" border-radius:4px; padding:6px 16px; }}"
            f"QPushButton:hover {{ background:#3A3A3A; }}"
        )
        self._stop_btn.clicked.connect(self._stop_scan)
        btn_row.addWidget(self._stop_btn)
        btn_row.addStretch()

        self._status_lbl = QLabel("Pronto")
        self._status_lbl.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px;")
        btn_row.addWidget(self._status_lbl)
        layout.addLayout(btn_row)

        # Progress
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        self._progress.setStyleSheet(f"""
            QProgressBar {{ background:#1E1E1E; border:1px solid #333;
                           border-radius:3px; height:6px; text-align:center; }}
            QProgressBar::chunk {{ background:{ACCENT_COLOR}; border-radius:3px; }}
        """)
        layout.addWidget(self._progress)

        # Tabella risultati
        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["IP", "Porta", "Servizio", "Aggiungi"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(1, 70)
        self._table.setColumnWidth(2, 100)
        self._table.setColumnWidth(3, 80)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(f"""
            QTableWidget {{ background:{BG_COLOR}; color:{TEXT_COLOR};
                           border:1px solid #2A2A2A; alternate-background-color:#111; }}
            QHeaderView::section {{ background:#1A1A1A; color:{SUB_COLOR};
                                    border:none; padding:4px 8px; font-size:11px; }}
            QTableWidget::item:selected {{ background:#1A3A5A; }}
            QCheckBox {{ margin-left:16px; }}
        """)
        layout.addWidget(self._table)

        # Footer
        footer = QHBoxLayout()
        footer.addStretch()
        self._add_selected_btn = QPushButton("Aggiungi selezionati alle connessioni")
        self._add_selected_btn.setEnabled(False)
        self._add_selected_btn.setStyleSheet(f"""
            QPushButton {{ background:#1A3A1A; color:#4EC94E; border:1px solid #2A4A2A;
                          border-radius:4px; padding:6px 14px; font-weight:bold; }}
            QPushButton:hover {{ background:#1E4A1E; }}
            QPushButton:disabled {{ background:#222; color:#444; border-color:#333; }}
        """)
        self._add_selected_btn.clicked.connect(self._add_selected)
        footer.addWidget(self._add_selected_btn)

        close_btn = QPushButton("Chiudi")
        close_btn.setStyleSheet(
            f"QPushButton {{ background:#2A2A2A; color:{TEXT_COLOR}; border:1px solid #444;"
            f" border-radius:4px; padding:6px 14px; }}"
            f"QPushButton:hover {{ background:#3A3A3A; }}"
        )
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        layout.addLayout(footer)

    def _get_ports(self) -> List[int]:
        idx = self._proto_combo.currentIndex()
        if idx == 0:
            return [22]
        if idx == 1:
            return [3389]
        if idx == 2:
            return list(COMMON_PORTS.keys())
        # Personalizzato
        raw = self._custom_ports_input.text()
        ports = []
        for p in raw.split(","):
            try:
                ports.append(int(p.strip()))
            except ValueError:
                pass
        return ports or [22]

    def _start_scan(self):
        subnet = self._subnet_input.text().strip()
        if not subnet:
            return
        ports = self._get_ports()
        self._found.clear()
        self._table.setRowCount(0)
        self._add_selected_btn.setEnabled(False)

        try:
            net = ipaddress.ip_network(subnet, strict=False)
            total = net.num_addresses - 2
        except ValueError:
            QMessageBox.warning(self, "Errore", "Subnet non valida (es. 192.168.1.0/24)")
            return

        self._progress.setRange(0, max(total, 1))
        self._progress.setValue(0)
        self._progress.setVisible(True)
        self._scan_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._status_lbl.setText("Scansione in corso...")

        self._worker = DiscoveryWorker(subnet, ports)
        self._worker.host_found.connect(self._on_host_found)
        self._worker.progress.connect(self._progress.setValue)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _stop_scan(self):
        if self._worker:
            self._worker.stop()

    def _on_host_found(self, ip: str, port: int, service: str):
        entry = {"ip": ip, "port": port, "service": service}
        self._found.append(entry)

        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(ip))
        self._table.setItem(row, 1, QTableWidgetItem(str(port)))
        svc_item = QTableWidgetItem(service)
        svc_item.setForeground(QColor(ACCENT_COLOR))
        self._table.setItem(row, 2, svc_item)

        cb = QCheckBox()
        cb.setChecked(True)
        cell = QWidget()
        cell_layout = QHBoxLayout(cell)
        cell_layout.addWidget(cb)
        cell_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cell_layout.setContentsMargins(0, 0, 0, 0)
        self._table.setCellWidget(row, 3, cell)
        entry["_cb"] = cb

        self._add_selected_btn.setEnabled(True)
        self._status_lbl.setText(f"{len(self._found)} host trovati")

    def _on_done(self):
        self._scan_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)
        self._progress.setVisible(False)
        self._status_lbl.setText(
            f"Completata. {len(self._found)} host trovati."
        )

    def _add_selected(self):
        selected = [e for e in self._found if e.get("_cb") and e["_cb"].isChecked()]
        if selected:
            self.hosts_to_add.emit(selected)
            QMessageBox.information(
                self, "Aggiunto",
                f"{len(selected)} host aggiunti alle connessioni."
            )
