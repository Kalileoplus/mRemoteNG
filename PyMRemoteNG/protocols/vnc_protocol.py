"""
Protocollo VNC - lancia un VNC viewer esterno.
"""
from __future__ import annotations
import subprocess
import os
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from protocols.base import ProtocolBase

if TYPE_CHECKING:
    from core.models import ConnectionInfo


class VNCProtocol(ProtocolBase):
    """Lancia TigerVNC o TightVNC come processo esterno."""

    VNC_VIEWERS = [
        "tvnviewer.exe", "vncviewer.exe", "tvnc.exe",  # Windows
        "vncviewer", "tigervncviewer", "xtightvncviewer"  # Linux/Mac
    ]

    def __init__(self, connection_info: 'ConnectionInfo', parent_widget: QWidget):
        super().__init__(connection_info, parent_widget)
        self._process: subprocess.Popen | None = None
        self._widget = self._build_widget()

    def _build_widget(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        self._label = QLabel("Avvio connessione VNC...")
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setStyleSheet("color: #888888; font-size: 14px;")
        layout.addWidget(self._label)
        return w

    def connect(self) -> bool:
        info = self.connection_info
        viewer = self._find_viewer()
        if not viewer:
            self._label.setText("Nessun VNC viewer trovato.\nInstalla TigerVNC o TightVNC.")
            return False
        try:
            from core.crypto import decrypt
            password = decrypt(info.password) if info.password else ""
            cmd = [viewer, f"{info.hostname}::{info.port}"]
            if password and "tigervnc" in viewer.lower() or "tvnc" in viewer.lower():
                cmd += ["-passwd", password]
            self._process = subprocess.Popen(cmd)
            self._label.setText(f"VNC avviato verso {info.hostname}:{info.port}")
            self.on_connected()
            return True
        except Exception as e:
            self._label.setText(f"Errore avvio VNC: {e}")
            return False

    def _find_viewer(self) -> str | None:
        for viewer in self.VNC_VIEWERS:
            try:
                result = subprocess.run(["where" if os.name == "nt" else "which", viewer],
                                        capture_output=True, text=True)
                if result.returncode == 0 and result.stdout.strip():
                    return result.stdout.strip().splitlines()[0]
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
