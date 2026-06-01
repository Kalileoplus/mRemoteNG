from protocols.base import ProtocolBase
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt


class UnsupportedProtocol(ProtocolBase):
    def connect(self) -> bool:
        return False

    def disconnect(self):
        pass

    def get_widget(self) -> QWidget:
        w = QWidget()
        lbl = QLabel(f"Protocollo '{self.connection_info.protocol.value}' non ancora supportato.")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: #888888; font-size: 13px;")
        QVBoxLayout(w).addWidget(lbl)
        return w
