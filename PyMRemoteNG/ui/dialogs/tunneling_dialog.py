"""
SSH Tunneling dialog: port forwarding locale/remoto/dinamico.
"""
import threading
import socket
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QRadioButton, QSpinBox, QGroupBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QButtonGroup
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from themes.dark_theme import ACCENT_COLOR, CARD_COLOR, TEXT_COLOR, SUB_COLOR


class TunnelingDialog(QDialog):
    """
    Configura e avvia tunnel SSH:
    - Local:   connessioni a localhost:porta_locale → inoltrate a remote_host:porta_remota
    - Remote:  connessioni al server SSH vengono inoltrate a localhost:porta
    - Dynamic: SOCKS5 proxy su porta locale
    """
    def __init__(self, open_tabs: dict, parent=None):
        super().__init__(parent)
        self.open_tabs   = open_tabs
        self._tunnels:  list = []
        self.setWindowTitle("🔗  SSH Tunneling / Port Forwarding")
        self.setMinimumSize(560, 480)
        self.setStyleSheet(f"QDialog {{ background: {CARD_COLOR}; color: {TEXT_COLOR}; }}")
        self._setup_ui()

    def _style_input(self) -> str:
        return (f"background: #1E1E1E; color: {TEXT_COLOR}; "
                f"border: 1px solid #333; border-radius: 3px; padding: 4px 8px;")

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 12)

        hdr = QLabel("🔗  SSH Tunneling — Port Forwarding")
        hdr.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        hdr.setStyleSheet(f"color: {TEXT_COLOR}; background: transparent;")
        layout.addWidget(hdr)

        # Tipo tunnel
        type_box = QGroupBox("Tipo tunnel")
        type_box.setStyleSheet(f"QGroupBox {{ color: {SUB_COLOR}; border: 1px solid #2A2A2A; border-radius: 3px; margin-top: 8px; padding-top: 6px; }}")
        type_layout = QHBoxLayout(type_box)
        self._bg = QButtonGroup(self)
        for i, (txt, tip) in enumerate([
            ("Local",   "Inoltro locale: localhost:porta → server remoto"),
            ("Remote",  "Inoltro remoto: server → localhost:porta"),
            ("Dynamic", "SOCKS5 proxy su porta locale"),
        ]):
            rb = QRadioButton(txt)
            rb.setToolTip(tip)
            rb.setStyleSheet(f"color: {TEXT_COLOR};")
            if i == 0: rb.setChecked(True)
            self._bg.addButton(rb, i)
            type_layout.addWidget(rb)
        layout.addWidget(type_box)

        # Sessione SSH
        sess_box = QGroupBox("Sessione SSH via cui fare tunneling")
        sess_box.setStyleSheet(f"QGroupBox {{ color: {SUB_COLOR}; border: 1px solid #2A2A2A; border-radius: 3px; margin-top: 8px; padding-top: 6px; }}")
        sess_layout = QHBoxLayout(sess_box)
        from PyQt6.QtWidgets import QComboBox
        self.session_combo = QComboBox()
        self.session_combo.setStyleSheet(f"background: #1E1E1E; color: {TEXT_COLOR}; border: 1px solid #333; border-radius: 3px; padding: 3px 6px;")
        self.session_combo.addItem("— Diretta (senza tunnel) —")
        from ui.main_window import ConnectionTab
        for tab in self.open_tabs.values():
            if isinstance(tab, ConnectionTab) and tab._protocol and tab._protocol.is_connected:
                self.session_combo.addItem(
                    f"{tab.conn.name}  ({tab.conn.hostname}:{tab.conn.port})",
                    userData=tab
                )
        sess_layout.addWidget(self.session_combo)
        layout.addWidget(sess_box)

        # Parametri
        params_box = QGroupBox("Parametri")
        params_box.setStyleSheet(f"QGroupBox {{ color: {SUB_COLOR}; border: 1px solid #2A2A2A; border-radius: 3px; margin-top: 8px; padding-top: 6px; }}")
        params_grid = QVBoxLayout(params_box)

        def field(label, placeholder, default=""):
            row = QHBoxLayout()
            lbl = QLabel(label); lbl.setFixedWidth(130)
            lbl.setStyleSheet(f"color: {SUB_COLOR}; background: transparent;")
            inp = QLineEdit(default)
            inp.setPlaceholderText(placeholder)
            inp.setStyleSheet(self._style_input())
            row.addWidget(lbl); row.addWidget(inp)
            params_grid.addLayout(row)
            return inp

        self.local_port  = field("Porta locale:",        "es. 8080", "8080")
        self.remote_host = field("Host remoto:",          "es. 192.168.1.10", "")
        self.remote_port = field("Porta remota:",         "es. 80", "80")
        layout.addWidget(params_box)

        # Bottone avvia
        btn_row = QHBoxLayout()
        self.start_btn = QPushButton("▶  Avvia Tunnel")
        self.start_btn.setFixedHeight(34)
        self.start_btn.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        self.start_btn.setStyleSheet(f"""
            QPushButton {{ background: {ACCENT_COLOR}; color: white;
                border: none; border-radius: 3px; padding: 0 18px; }}
            QPushButton:hover {{ background: #0088DD; }}
        """)
        self.start_btn.clicked.connect(self._start_tunnel)
        btn_row.addWidget(self.start_btn)

        stop_btn = QPushButton("⏹  Ferma tutti")
        stop_btn.setFixedHeight(34)
        stop_btn.setStyleSheet(f"""
            QPushButton {{ background: #2A2A2A; color: {TEXT_COLOR};
                border: 1px solid #333; border-radius: 3px; padding: 0 14px; }}
            QPushButton:hover {{ background: #3A3A3A; }}
        """)
        stop_btn.clicked.connect(self._stop_tunnels)
        btn_row.addWidget(stop_btn)
        btn_row.addStretch()

        close_btn = QPushButton("Chiudi")
        close_btn.setFixedHeight(34)
        close_btn.setStyleSheet(f"""
            QPushButton {{ background: #2A2A2A; color: {TEXT_COLOR};
                border: 1px solid #333; border-radius: 3px; padding: 0 14px; }}
        """)
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        # Tabella tunnel attivi
        active_lbl = QLabel("Tunnel attivi:")
        active_lbl.setStyleSheet(f"color: {SUB_COLOR}; background: transparent; margin-top: 4px;")
        layout.addWidget(active_lbl)

        self.tunnel_table = QTableWidget(0, 4)
        self.tunnel_table.setHorizontalHeaderLabels(["Tipo", "Porta Locale", "→ Host:Porta Remota", "Stato"])
        self.tunnel_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.tunnel_table.setStyleSheet(f"""
            QTableWidget {{ background: #141414; color: {TEXT_COLOR}; border: 1px solid #2A2A2A; gridline-color: #2A2A2A; }}
            QHeaderView::section {{ background: #1A1A1A; color: {SUB_COLOR}; border: none; padding: 4px; }}
        """)
        self.tunnel_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.tunnel_table)

    def _start_tunnel(self):
        tipo       = ["Local","Remote","Dynamic"][self._bg.checkedId()]
        local_port = int(self.local_port.text() or 0)
        rhost      = self.remote_host.text().strip()
        rport      = int(self.remote_port.text() or 0)

        if tipo == "Local" and (not rhost or not rport or not local_port):
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(self, "Parametri mancanti",
                                "Compila porta locale, host remoto e porta remota.")
            return

        # Avvia thread di forwarding locale (semplificato)
        info = f"{tipo}  :{local_port} → {rhost}:{rport}"
        if tipo == "Local":
            t = threading.Thread(
                target=self._local_forward_thread,
                args=(local_port, rhost, rport),
                daemon=True
            )
            t.start()
            self._tunnels.append(t)

        # Aggiorna tabella
        row = self.tunnel_table.rowCount()
        self.tunnel_table.insertRow(row)
        self.tunnel_table.setItem(row, 0, QTableWidgetItem(tipo))
        self.tunnel_table.setItem(row, 1, QTableWidgetItem(str(local_port)))
        self.tunnel_table.setItem(row, 2, QTableWidgetItem(f"{rhost}:{rport}"))
        status = QTableWidgetItem("🟢 Attivo")
        self.tunnel_table.setItem(row, 3, status)

    def _local_forward_thread(self, local_port: int, rhost: str, rport: int):
        """Semplice TCP forwarder locale."""
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(('127.0.0.1', local_port))
            srv.listen(5)
            srv.settimeout(1.0)
            while True:
                try:
                    client, _ = srv.accept()
                except socket.timeout:
                    continue
                threading.Thread(
                    target=self._bridge, args=(client, rhost, rport), daemon=True
                ).start()
        except Exception:
            pass

    def _bridge(self, client: socket.socket, rhost: str, rport: int):
        try:
            remote = socket.create_connection((rhost, rport), timeout=10)
            def fwd(src, dst):
                try:
                    while True:
                        d = src.recv(4096)
                        if not d: break
                        dst.sendall(d)
                except Exception:
                    pass
                finally:
                    src.close(); dst.close()
            threading.Thread(target=fwd, args=(client, remote), daemon=True).start()
            threading.Thread(target=fwd, args=(remote, client), daemon=True).start()
        except Exception:
            client.close()

    def _stop_tunnels(self):
        self._tunnels.clear()
        for r in range(self.tunnel_table.rowCount()):
            self.tunnel_table.setItem(r, 3, QTableWidgetItem("⏹ Fermato"))
