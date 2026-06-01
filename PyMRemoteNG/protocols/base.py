"""
Classe base per tutti i protocolli di connessione.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
from PyQt6.QtWidgets import QWidget

if TYPE_CHECKING:
    from core.models import ConnectionInfo


class ProtocolBase(ABC):
    """Base class per tutti i protocolli - equivalente di ProtocolBase.cs"""

    def __init__(self, connection_info: 'ConnectionInfo', parent_widget: QWidget):
        self.connection_info = connection_info
        self.parent_widget   = parent_widget
        self._connected      = False

    @abstractmethod
    def connect(self) -> bool:
        """Avvia la connessione. Restituisce True se ok."""
        ...

    @abstractmethod
    def disconnect(self):
        """Chiude la connessione."""
        ...

    @abstractmethod
    def get_widget(self) -> QWidget:
        """Restituisce il widget da embeddare nel tab."""
        ...

    @property
    def is_connected(self) -> bool:
        return self._connected

    def on_connected(self):
        self._connected = True

    def on_disconnected(self):
        self._connected = False

    def send_special_keys(self, keys: str):
        """Invia tasti speciali (usato da MultiSSH)."""
        pass
