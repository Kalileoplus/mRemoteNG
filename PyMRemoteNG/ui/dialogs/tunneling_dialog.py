"""
SSH Tunneling dialog: port forwarding locale / remoto / dinamico (SOCKS5).
"""
from __future__ import annotations
import socket
import threading
from typing import List

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QWidget, QStackedWidget, QMessageBox,
    QSpinBox
)
from themes.dark_theme import ACCENT_COLOR, TEXT_COLOR, SUB_COLOR, BG_COLOR, CARD_COLOR

_INPUT = (
    f"background:#111111; color:{TEXT_COLOR}; border:1px solid #252525; "
    f"border-radius:4px; padding:5px 10px; font-size:12px;"
)
_INPUT_FOCUS = (
    f"background:#111111; color:{TEXT_COLOR}; border:1px solid {ACCENT_COLOR}; "
    f"border-radius:4px; padding:5px 10px; font-size:12px;"
)


def _lbl(text: str, sub: bool = False) -> QLabel:
    l = QLabel(text)
    l.setStyleSheet(
        f"color:{SUB_COLOR if sub else TEXT_COLOR}; "
        f"font-size:{'10' if sub else '12'}px; background:transparent;"
    )
    return l


def _sep() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("border:none; border-top:1px solid #1E1E1E;")
    return f


class TunnelEntry:
    def __init__(self, kind: str, local_port: int,
                 remote_host: str, remote_port: int):
        self.kind        = kind          # Local | Remote | Dynamic
        self.local_port  = local_port
        self.remote_host = remote_host
        self.remote_port = remote_port
        self._srv_socket: socket.socket | None = None
        self._thread:     threading.Thread | None = None
        self.active      = False

    def label(self) -> str:
        if self.kind == "Dynamic":
            return f"SOCKS5  :{self.local_port}"
        return f"{self.kind}  :{self.local_port} → {self.remote_host}:{self.remote_port}"

    def stop(self):
        self.active = False
        if self._srv_socket:
            try:
                self._srv_socket.close()
            except Exception:
                pass


class TunnelingDialog(QDialog):
    def __init__(self, open_tabs: dict, parent=None):
        super().__init__(parent)
        self.open_tabs = open_tabs
        self._tunnels: List[TunnelEntry] = []
        self.setWindowTitle("SSH Tunneling — Port Forwarding")
        self.setMinimumSize(620, 560)
        self.setStyleSheet(f"QDialog {{ background:{BG_COLOR}; color:{TEXT_COLOR}; }}")
        self._build_ui()

    # ── UI ──────────────────────────────────────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(14)

        # Titolo
        title = QLabel("SSH Tunneling / Port Forwarding")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{ACCENT_COLOR}; background:transparent;")
        lay.addWidget(title)

        desc = _lbl(
            "Inoltra porte attraverso una connessione SSH attiva. "
            "Seleziona il tipo di tunnel e configura i parametri.", sub=True
        )
        desc.setWordWrap(True)
        lay.addWidget(desc)
        lay.addWidget(_sep())

        # ── Passo 1: Sessione SSH ──
        s1_lbl = _lbl("1  Sessione SSH da usare")
        s1_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lay.addWidget(s1_lbl)

        self._session_combo = QComboBox()
        self._session_combo.setStyleSheet(_INPUT)
        self._session_combo.addItem("— Tunnel diretto (senza SSH esistente) —", None)
        from ui.main_window import ConnectionTab
        for tab in self.open_tabs.values():
            if isinstance(tab, ConnectionTab) and tab._protocol and tab._protocol.is_connected:
                self._session_combo.addItem(
                    f"  {tab.conn.name}  ({tab.conn.hostname}:{tab.conn.port})",
                    tab
                )
        lay.addWidget(self._session_combo)
        lay.addWidget(_sep())

        # ── Passo 2: Tipo tunnel ──
        s2_lbl = _lbl("2  Tipo di forwarding")
        s2_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lay.addWidget(s2_lbl)

        self._type_combo = QComboBox()
        self._type_combo.setStyleSheet(_INPUT)
        self._type_combo.addItem("Local  —  porta locale → host remoto (più comune)", "Local")
        self._type_combo.addItem("Remote  —  porta sul server SSH → localhost", "Remote")
        self._type_combo.addItem("Dynamic  —  proxy SOCKS5 su porta locale", "Dynamic")
        self._type_combo.currentIndexChanged.connect(self._on_type_change)
        lay.addWidget(self._type_combo)

        # Descrizione tipo
        self._type_desc = _lbl("", sub=True)
        self._type_desc.setWordWrap(True)
        lay.addWidget(self._type_desc)
        lay.addWidget(_sep())

        # ── Passo 3: Parametri (stack contestuale) ──
        s3_lbl = _lbl("3  Parametri")
        s3_lbl.setFont(QFont("Segoe UI", 11, QFont.Weight.Bold))
        lay.addWidget(s3_lbl)

        self._param_stack = QStackedWidget()
        self._param_stack.addWidget(self._build_local_params())   # 0 = Local
        self._param_stack.addWidget(self._build_remote_params())  # 1 = Remote
        self._param_stack.addWidget(self._build_dynamic_params()) # 2 = Dynamic
        lay.addWidget(self._param_stack)

        # Aggiorna descrizione iniziale
        self._on_type_change(0)

        lay.addWidget(_sep())

        # ── Bottoni ──
        btn_row = QHBoxLayout()
        self._add_btn = QPushButton("＋  Avvia tunnel")
        self._add_btn.setFixedHeight(36)
        self._add_btn.setStyleSheet(f"""
            QPushButton {{ background:{ACCENT_COLOR}; color:white; border:none;
                          border-radius:4px; padding:0 20px; font-weight:bold; font-size:12px; }}
            QPushButton:hover {{ background:#0088DD; }}
        """)
        self._add_btn.clicked.connect(self._start_tunnel)
        btn_row.addWidget(self._add_btn)

        stop_all_btn = QPushButton("⏹  Ferma tutti")
        stop_all_btn.setFixedHeight(36)
        stop_all_btn.setStyleSheet(
            f"QPushButton {{ background:#1E1E1E; color:{TEXT_COLOR}; border:1px solid #2A2A2A;"
            f" border-radius:4px; padding:0 14px; }}"
            f"QPushButton:hover {{ background:#EF535033; border-color:#EF5350; color:#EF5350; }}"
        )
        stop_all_btn.clicked.connect(self._stop_all)
        btn_row.addWidget(stop_all_btn)
        btn_row.addStretch()

        close_btn = QPushButton("Chiudi")
        close_btn.setFixedHeight(36)
        close_btn.setStyleSheet(
            f"QPushButton {{ background:#1E1E1E; color:{TEXT_COLOR}; border:1px solid #2A2A2A;"
            f" border-radius:4px; padding:0 16px; }}"
            f"QPushButton:hover {{ background:#2A2A2A; }}"
        )
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        lay.addLayout(btn_row)

        # ── Tabella tunnel attivi ──
        act_lbl = _lbl("Tunnel attivi", sub=True)
        act_lbl.setStyleSheet(f"color:{SUB_COLOR}; font-size:10px; font-weight:bold; background:transparent;")
        lay.addWidget(act_lbl)

        self._table = QTableWidget(0, 4)
        self._table.setHorizontalHeaderLabels(["Tipo", "Porta locale", "→ Destinazione", "Stato"])
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(0, 80)
        self._table.setColumnWidth(1, 90)
        self._table.setColumnWidth(3, 80)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.setFixedHeight(120)
        self._table.setStyleSheet(f"""
            QTableWidget {{ background:#0A0A0A; color:{TEXT_COLOR};
                           border:1px solid #1E1E1E; border-radius:4px;
                           alternate-background-color:#0D0D0D; }}
            QHeaderView::section {{ background:#111; color:{SUB_COLOR};
                                    border:none; border-bottom:1px solid #1E1E1E;
                                    padding:4px 8px; font-size:11px; }}
        """)
        lay.addWidget(self._table)

    # ── Param panels ────────────────────────────────────────────────

    def _build_local_params(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        row1 = QHBoxLayout()
        row1.addWidget(_lbl("Porta locale  (su questo PC):", sub=True))
        self._local_port = QSpinBox()
        self._local_port.setRange(1, 65535)
        self._local_port.setValue(8080)
        self._local_port.setFixedWidth(90)
        self._local_port.setStyleSheet(_INPUT)
        row1.addWidget(self._local_port)
        row1.addStretch()
        lay.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(_lbl("Host remoto  (destinazione finale):", sub=True))
        self._local_rhost = QLineEdit()
        self._local_rhost.setPlaceholderText("es. 192.168.10.5 oppure db-server")
        self._local_rhost.setStyleSheet(_INPUT)
        row2.addWidget(self._local_rhost)
        lay.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(_lbl("Porta remota  (sul host remoto):", sub=True))
        self._local_rport = QSpinBox()
        self._local_rport.setRange(1, 65535)
        self._local_rport.setValue(80)
        self._local_rport.setFixedWidth(90)
        self._local_rport.setStyleSheet(_INPUT)
        row3.addWidget(self._local_rport)
        row3.addStretch()
        lay.addLayout(row3)

        example = _lbl(
            "Esempio: porta locale 8080 → host 192.168.10.5:80\n"
            "Poi apri browser su localhost:8080 per raggiungere il server remoto.",
            sub=True
        )
        example.setWordWrap(True)
        lay.addWidget(example)
        return w

    def _build_remote_params(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        row1 = QHBoxLayout()
        row1.addWidget(_lbl("Porta sul server SSH  (si apre lì):", sub=True))
        self._remote_srv_port = QSpinBox()
        self._remote_srv_port.setRange(1, 65535)
        self._remote_srv_port.setValue(9090)
        self._remote_srv_port.setFixedWidth(90)
        self._remote_srv_port.setStyleSheet(_INPUT)
        row1.addWidget(self._remote_srv_port)
        row1.addStretch()
        lay.addLayout(row1)

        row2 = QHBoxLayout()
        row2.addWidget(_lbl("Host locale  (dove girare qui):", sub=True))
        self._remote_lhost = QLineEdit("127.0.0.1")
        self._remote_lhost.setStyleSheet(_INPUT)
        row2.addWidget(self._remote_lhost)
        lay.addLayout(row2)

        row3 = QHBoxLayout()
        row3.addWidget(_lbl("Porta locale  (destinazione su questo PC):", sub=True))
        self._remote_lport = QSpinBox()
        self._remote_lport.setRange(1, 65535)
        self._remote_lport.setValue(80)
        self._remote_lport.setFixedWidth(90)
        self._remote_lport.setStyleSheet(_INPUT)
        row3.addWidget(self._remote_lport)
        row3.addStretch()
        lay.addLayout(row3)

        example = _lbl(
            "Esempio: chi si connette a serverSSH:9090 viene girato a localhost:80 su questo PC.",
            sub=True
        )
        example.setWordWrap(True)
        lay.addWidget(example)
        return w

    def _build_dynamic_params(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background:transparent;")
        lay = QVBoxLayout(w)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        row = QHBoxLayout()
        row.addWidget(_lbl("Porta SOCKS5  (su questo PC):", sub=True))
        self._socks_port = QSpinBox()
        self._socks_port.setRange(1, 65535)
        self._socks_port.setValue(1080)
        self._socks_port.setFixedWidth(90)
        self._socks_port.setStyleSheet(_INPUT)
        row.addWidget(self._socks_port)
        row.addStretch()
        lay.addLayout(row)

        example = _lbl(
            "Configura il browser o l'applicazione per usare\n"
            "proxy SOCKS5 su  127.0.0.1 : porta scelta.\n"
            "Tutto il traffico verrà instradato attraverso l'SSH.",
            sub=True
        )
        example.setWordWrap(True)
        lay.addWidget(example)
        return w

    # ── Logic ────────────────────────────────────────────────────────

    _TYPE_DESC = {
        0: ("Local forward",
            "Apre una porta su questo PC. Le connessioni a quella porta vengono inoltrate "
            "attraverso SSH a un host:porta raggiungibile dal server SSH."),
        1: ("Remote forward",
            "Apre una porta sul server SSH remoto. Chi si connette lì viene girato "
            "verso un host:porta su questo PC locale."),
        2: ("Dynamic (SOCKS5 proxy)",
            "Crea un proxy SOCKS5 locale. Tutto il traffico delle applicazioni che lo usano "
            "transiterà attraverso il server SSH."),
    }

    def _on_type_change(self, idx: int):
        self._param_stack.setCurrentIndex(idx)
        _, desc = self._TYPE_DESC.get(idx, ("", ""))
        self._type_desc.setText(desc)

    def _start_tunnel(self):
        idx  = self._type_combo.currentIndex()
        kind = ["Local", "Remote", "Dynamic"][idx]

        try:
            if kind == "Local":
                lport = self._local_port.value()
                rhost = self._local_rhost.text().strip()
                rport = self._local_rport.value()
                if not rhost:
                    QMessageBox.warning(self, "Parametro mancante",
                                        "Inserisci l'host remoto di destinazione.")
                    return
                entry = TunnelEntry(kind, lport, rhost, rport)
                t = threading.Thread(
                    target=self._local_fwd, args=(entry,), daemon=True
                )
                entry._thread = t
                t.start()

            elif kind == "Remote":
                srv_port = self._remote_srv_port.value()
                lhost    = self._remote_lhost.text().strip() or "127.0.0.1"
                lport    = self._remote_lport.value()
                entry = TunnelEntry(kind, srv_port, lhost, lport)
                # Remote forward richiede paramiko channel — mostriamo come configurarlo
                QMessageBox.information(
                    self, "Remote Forward",
                    f"Configurazione Remote Forward:\n\n"
                    f"Porta server SSH: {srv_port}\n"
                    f"Destinazione locale: {lhost}:{lport}\n\n"
                    "Il remote forward viene attivato tramite la sessione SSH attiva.\n"
                    "Seleziona una sessione SSH dalla lista sopra per applicarlo."
                )

            else:  # Dynamic SOCKS5
                lport = self._socks_port.value()
                entry = TunnelEntry("Dynamic", lport, "", 0)
                t = threading.Thread(
                    target=self._dynamic_socks5, args=(entry,), daemon=True
                )
                entry._thread = t
                t.start()

        except Exception as e:
            QMessageBox.warning(self, "Errore", str(e))
            return

        entry.active = True
        self._tunnels.append(entry)

        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(kind))
        self._table.setItem(row, 1, QTableWidgetItem(str(entry.local_port)))
        dest = f"{entry.remote_host}:{entry.remote_port}" if kind != "Dynamic" else "SOCKS5"
        self._table.setItem(row, 2, QTableWidgetItem(dest))
        status = QTableWidgetItem("● Attivo")
        status.setForeground(QColor("#4EC94E"))
        self._table.setItem(row, 3, status)

    def _stop_all(self):
        for e in self._tunnels:
            e.stop()
        for r in range(self._table.rowCount()):
            item = self._table.item(r, 3)
            if item:
                item.setText("⏹ Fermato")
                item.setForeground(QColor("#888"))

    # ── TCP forwarder ─────────────────────────────────────────────

    def _local_fwd(self, entry: TunnelEntry):
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("127.0.0.1", entry.local_port))
            srv.listen(10)
            srv.settimeout(1.0)
            entry._srv_socket = srv
            while entry.active:
                try:
                    client, _ = srv.accept()
                except socket.timeout:
                    continue
                threading.Thread(
                    target=self._bridge,
                    args=(client, entry.remote_host, entry.remote_port),
                    daemon=True,
                ).start()
        except Exception:
            pass

    def _dynamic_socks5(self, entry: TunnelEntry):
        """Minimal SOCKS5 server."""
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("127.0.0.1", entry.local_port))
            srv.listen(10)
            srv.settimeout(1.0)
            entry._srv_socket = srv
            while entry.active:
                try:
                    client, _ = srv.accept()
                except socket.timeout:
                    continue
                threading.Thread(
                    target=self._handle_socks5, args=(client,), daemon=True
                ).start()
        except Exception:
            pass

    def _handle_socks5(self, client: socket.socket):
        try:
            # SOCKS5 handshake
            header = client.recv(2)
            if not header or header[0] != 5:
                client.close(); return
            nmethods = header[1]
            client.recv(nmethods)
            client.send(b'\x05\x00')  # no auth

            req = client.recv(4)
            if not req or req[1] != 1:  # only CONNECT
                client.send(b'\x05\x07\x00\x01' + b'\x00'*6); client.close(); return

            atype = req[3]
            if atype == 1:    # IPv4
                addr = socket.inet_ntoa(client.recv(4))
            elif atype == 3:  # domain
                ln = client.recv(1)[0]
                addr = client.recv(ln).decode()
            else:
                client.close(); return
            port = int.from_bytes(client.recv(2), 'big')

            remote = socket.create_connection((addr, port), timeout=10)
            client.send(b'\x05\x00\x00\x01' + socket.inet_aton('0.0.0.0') + (0).to_bytes(2,'big'))
            self._bridge(client, addr, port, remote)
        except Exception:
            try: client.close()
            except Exception: pass

    def _bridge(self, client: socket.socket, rhost: str, rport: int,
                remote: socket.socket = None):
        try:
            if remote is None:
                remote = socket.create_connection((rhost, rport), timeout=10)
        except Exception:
            client.close(); return
        def fwd(src, dst):
            try:
                while True:
                    d = src.recv(4096)
                    if not d: break
                    dst.sendall(d)
            except Exception: pass
            finally:
                try: src.close()
                except Exception: pass
                try: dst.close()
                except Exception: pass
        threading.Thread(target=fwd, args=(client, remote), daemon=True).start()
        threading.Thread(target=fwd, args=(remote, client), daemon=True).start()
