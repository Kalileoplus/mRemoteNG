"""
Factory per la creazione dei protocolli in base al tipo di connessione.
"""
from __future__ import annotations
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QWidget
from core.models import ProtocolType
from protocols.base import ProtocolBase

if TYPE_CHECKING:
    from core.models import ConnectionInfo


def create_protocol(info: 'ConnectionInfo', parent: QWidget) -> ProtocolBase:
    """Istanzia il protocollo corretto per la connessione."""
    p = info.protocol

    if p == ProtocolType.SSH2:
        from protocols.ssh_protocol import SSHProtocol
        return SSHProtocol(info, parent)

    elif p == ProtocolType.RDP:
        from protocols.rdp_protocol import RDPProtocol
        return RDPProtocol(info, parent)

    elif p in (ProtocolType.VNC, ProtocolType.ARD):
        from protocols.vnc_protocol import VNCProtocol
        return VNCProtocol(info, parent)

    elif p in (ProtocolType.HTTP, ProtocolType.HTTPS):
        from protocols.http_protocol import HTTPProtocol
        return HTTPProtocol(info, parent)

    elif p in (ProtocolType.Telnet, ProtocolType.Rlogin, ProtocolType.RAW):
        from protocols.putty_protocol import PuttyProtocol
        return PuttyProtocol(info, parent)

    else:
        from protocols.unsupported_protocol import UnsupportedProtocol
        return UnsupportedProtocol(info, parent)
