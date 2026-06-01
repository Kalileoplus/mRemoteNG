"""
Protocollo HTTP/HTTPS - browser integrato via QWebEngineView.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QWidget, QVBoxLayout
from PyQt6.QtCore import QUrl
from protocols.base import ProtocolBase

try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    HAS_WEBENGINE = True
except ImportError:
    HAS_WEBENGINE = False

if TYPE_CHECKING:
    from core.models import ConnectionInfo


class HTTPProtocol(ProtocolBase):
    """Browser embedded per HTTP/HTTPS."""

    def __init__(self, connection_info: 'ConnectionInfo', parent_widget: QWidget):
        super().__init__(connection_info, parent_widget)
        self._widget = self._build_widget()

    def _build_widget(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        if HAS_WEBENGINE:
            self._browser = QWebEngineView()
            layout.addWidget(self._browser)
        else:
            from PyQt6.QtWidgets import QLabel
            from PyQt6.QtCore import Qt
            lbl = QLabel("PyQt6-WebEngine non installato.\nEsegui: pip install PyQt6-WebEngine")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet("color: #888888;")
            layout.addWidget(lbl)
            self._browser = None
        return w

    def connect(self) -> bool:
        info = self.connection_info
        scheme = "https" if info.protocol.value == "HTTPS" else "http"
        port = info.port
        default_ports = {"http": 80, "https": 443}
        if port and port != default_ports.get(scheme):
            url = f"{scheme}://{info.hostname}:{port}"
        else:
            url = f"{scheme}://{info.hostname}"
        if self._browser:
            self._browser.load(QUrl(url))
        self.on_connected()
        return True

    def disconnect(self):
        if self._browser:
            self._browser.load(QUrl("about:blank"))
        self.on_disconnected()

    def get_widget(self) -> QWidget:
        return self._widget
