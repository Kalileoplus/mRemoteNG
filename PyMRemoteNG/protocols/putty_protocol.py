"""
Protocollo PuTTY-based (Telnet, Rlogin, RAW) - lancia PuTTY come processo.
"""
from __future__ import annotations
import re as _re
import subprocess
import os
from typing import TYPE_CHECKING
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from protocols.base import ProtocolBase

_HOSTNAME_RE = _re.compile(r'^[a-zA-Z0-9.\-_\[\]:]+$')
_CTRL_RE     = _re.compile(r'[\x00-\x1f\x7f]')

if TYPE_CHECKING:
    from core.models import ConnectionInfo


class PuttyProtocol(ProtocolBase):
    PUTTY_PATHS = [
        r"C:\Program Files\PuTTY\putty.exe",
        r"C:\Program Files (x86)\PuTTY\putty.exe",
        "putty.exe", "putty",
    ]

    def __init__(self, connection_info: 'ConnectionInfo', parent_widget: QWidget):
        super().__init__(connection_info, parent_widget)
        self._process: subprocess.Popen | None = None
        self._widget = self._build_widget()

    def _build_widget(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        self._label = QLabel("Avvio connessione PuTTY...")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("color: #888888; font-size: 14px;")
        layout.addWidget(self._label)
        return w

    def connect(self) -> bool:
        info = self.connection_info
        putty = self._find_putty()
        if not putty:
            self._label.setText("PuTTY non trovato.\nScarica PuTTY da putty.org")
            return False
        try:
            hostname = (info.hostname or "").strip()
            if not hostname or not _HOSTNAME_RE.match(hostname):
                self._label.setText("Hostname non valido.")
                return False
            from core.models import ProtocolType
            proto_flag = {
                ProtocolType.Telnet: "-telnet",
                ProtocolType.Rlogin: "-rlogin",
                ProtocolType.RAW:    "-raw",
            }.get(info.protocol, "-ssh")
            cmd = [putty, proto_flag, hostname, "-P", str(info.port)]
            if info.username:
                safe_user = _CTRL_RE.sub('', info.username)[:256]
                if safe_user:
                    cmd += ["-l", safe_user]
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            self._process = subprocess.Popen(cmd, creationflags=flags, close_fds=True)
            self._label.setText(f"PuTTY avviato: {info.protocol.value} → {hostname}:{info.port}")
            self.on_connected()
            return True
        except Exception as e:
            self._label.setText(f"Errore: {e}")
            return False

    def _find_putty(self) -> str | None:
        for path in self.PUTTY_PATHS:
            if os.path.isfile(path):
                return path
        try:
            r = subprocess.run(["where" if os.name == "nt" else "which", "putty"],
                               capture_output=True, text=True)
            if r.returncode == 0:
                return r.stdout.strip().splitlines()[0]
        except Exception:
            pass
        return None

    def disconnect(self):
        if self._process:
            try:
                self._process.terminate()
            except Exception:
                pass
        self.on_disconnected()

    def get_widget(self) -> QWidget:
        return self._widget
