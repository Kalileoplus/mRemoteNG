"""
Protocollo VNC - lancia un VNC viewer esterno.

VULN-15 fix: la password non viene mai passata come argomento di cmdline.
Per TigerVNC/TightVNC viene scritto un file .vnc temporaneo (formato DES standard)
con permessi 0600, cancellato automaticamente dopo l'avvio del viewer.
"""
from __future__ import annotations
import os
import re as _re
import subprocess
import tempfile
import threading
import time
from typing import TYPE_CHECKING

_HOSTNAME_RE = _re.compile(r'^[a-zA-Z0-9.\-_\[\]:]+$')

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt
from protocols.base import ProtocolBase

if TYPE_CHECKING:
    from core.models import ConnectionInfo


# ── Implementazione DES minimale per formato .vnc ────────────────────────────
# Necessaria perché TigerVNC richiede il file password nel formato VNC (DES)
# e la libreria `cryptography` non supporta single-DES.

_IP  = [58,50,42,34,26,18,10,2, 60,52,44,36,28,20,12,4,
        62,54,46,38,30,22,14,6, 64,56,48,40,32,24,16,8,
        57,49,41,33,25,17,9,1,  59,51,43,35,27,19,11,3,
        61,53,45,37,29,21,13,5, 63,55,47,39,31,23,15,7]
_FP  = [40,8,48,16,56,24,64,32, 39,7,47,15,55,23,63,31,
        38,6,46,14,54,22,62,30, 37,5,45,13,53,21,61,29,
        36,4,44,12,52,20,60,28, 35,3,43,11,51,19,59,27,
        34,2,42,10,50,18,58,26, 33,1,41,9,49,17,57,25]
_E   = [32,1,2,3,4,5,   4,5,6,7,8,9,   8,9,10,11,12,13,
        12,13,14,15,16,17, 16,17,18,19,20,21, 20,21,22,23,24,25,
        24,25,26,27,28,29, 28,29,30,31,32,1]
_P   = [16,7,20,21,29,12,28,17, 1,15,23,26,5,18,31,10,
        2,8,24,14,32,27,3,9, 19,13,30,6,22,11,4,25]
_PC1 = [57,49,41,33,25,17,9, 1,58,50,42,34,26,18, 10,2,59,51,43,35,27,
        19,11,3,60,52,44,36, 63,55,47,39,31,23,15, 7,62,54,46,38,30,22,
        14,6,61,53,45,37,29, 21,13,5,28,20,12,4]
_PC2 = [14,17,11,24,1,5, 3,28,15,6,21,10, 23,19,12,4,26,8,
        16,7,27,20,13,2, 41,52,31,37,47,55, 30,40,51,45,33,48,
        44,49,39,56,34,53, 46,42,50,36,29,32]
_SHIFTS = [1,1,2,2,2,2,2,2,1,2,2,2,2,2,2,1]
_SBOX = [
    [14,4,13,1,2,15,11,8,3,10,6,12,5,9,0,7,
     0,15,7,4,14,2,13,1,10,6,12,11,9,5,3,8,
     4,1,14,8,13,6,2,11,15,12,9,7,3,10,5,0,
     15,12,8,2,4,9,1,7,5,11,3,14,10,0,6,13],
    [15,1,8,14,6,11,3,4,9,7,2,13,12,0,5,10,
     3,13,4,7,15,2,8,14,12,0,1,10,6,9,11,5,
     0,14,7,11,10,4,13,1,5,8,12,6,9,3,2,15,
     13,8,10,1,3,15,4,2,11,6,7,12,0,5,14,9],
    [10,0,9,14,6,3,15,5,1,13,12,7,11,4,2,8,
     13,7,0,9,3,4,6,10,2,8,5,14,12,11,15,1,
     13,6,4,9,8,15,3,0,11,1,2,12,5,10,14,7,
     1,10,13,0,6,9,8,7,4,15,14,3,11,5,2,12],
    [7,13,14,3,0,6,9,10,1,2,8,5,11,12,4,15,
     13,8,11,5,6,15,0,3,4,7,2,12,1,10,14,9,
     10,6,9,0,12,11,7,13,15,1,3,14,5,2,8,4,
     3,15,0,6,10,1,13,8,9,4,5,11,12,7,2,14],
    [2,12,4,1,7,10,11,6,8,5,3,15,13,0,14,9,
     14,11,2,12,4,7,13,1,5,0,15,10,3,9,8,6,
     4,2,1,11,10,13,7,8,15,9,12,5,6,3,0,14,
     11,8,12,7,1,14,2,13,6,15,0,9,10,4,5,3],
    [12,1,10,15,9,2,6,8,0,13,3,4,14,7,5,11,
     10,15,4,2,7,12,9,5,6,1,13,14,0,11,3,8,
     9,14,15,5,2,8,12,3,7,0,4,10,1,13,11,6,
     4,3,2,12,9,5,15,10,11,14,1,7,6,0,8,13],
    [4,11,2,14,15,0,8,13,3,12,9,7,5,10,6,1,
     13,0,11,7,4,9,1,10,14,3,5,12,2,15,8,6,
     1,4,11,13,12,3,7,14,10,15,6,8,0,5,9,2,
     6,11,13,8,1,4,10,7,9,5,0,15,14,2,3,12],
    [13,2,8,4,6,15,11,1,10,9,3,14,5,0,12,7,
     1,15,13,8,10,3,7,4,12,5,6,11,0,14,9,2,
     7,11,4,1,9,12,14,2,0,6,10,13,15,3,5,8,
     2,1,14,7,4,10,8,13,15,12,9,0,3,5,6,11],
]


def _perm(block: int, table: list, in_bits: int) -> int:
    out = 0
    for pos in table:
        out = (out << 1) | ((block >> (in_bits - pos)) & 1)
    return out


def _des_encrypt_block(plaintext: bytes, key: bytes) -> bytes:
    """DES-ECB encrypt single 8-byte block (pure Python)."""
    # Key schedule
    k56 = _perm(int.from_bytes(key, 'big'), _PC1, 64)
    c, d = k56 >> 28, k56 & 0x0FFFFFFF
    subkeys = []
    for sh in _SHIFTS:
        c = ((c << sh) | (c >> (28 - sh))) & 0x0FFFFFFF
        d = ((d << sh) | (d >> (28 - sh))) & 0x0FFFFFFF
        subkeys.append(_perm((c << 28) | d, _PC2, 56))

    # Feistel rounds
    block = _perm(int.from_bytes(plaintext, 'big'), _IP, 64)
    l, r  = block >> 32, block & 0xFFFFFFFF
    for sk in subkeys:
        expanded = _perm(r, _E, 32)
        xored    = expanded ^ sk
        sb_out   = 0
        for i in range(8):
            chunk  = (xored >> (42 - 6 * i)) & 0x3F
            row    = ((chunk & 0x20) >> 4) | (chunk & 0x01)
            col    = (chunk >> 1) & 0x0F
            sb_out = (sb_out << 4) | _SBOX[i][row * 16 + col]
        l, r = r, l ^ _perm(sb_out, _P, 32)

    result = _perm((r << 32) | l, _FP, 64)
    return result.to_bytes(8, 'big')


def _vnc_des_encrypt(password: str) -> bytes:
    """Restituisce gli 8 byte del formato .vnc (DES, chiave a bit invertiti)."""
    pw  = (password.encode('latin-1', errors='replace') + b'\x00' * 8)[:8]
    key = bytes(int(f'{b:08b}'[::-1], 2) for b in pw)
    return _des_encrypt_block(b'\x00' * 8, key)


def _write_vnc_password_file(password: str) -> str:
    """Scrive il file password VNC (formato DES) con permessi owner-only.
    umask 0o077 elimina la race condition tra mkstemp e chmod."""
    try:
        encrypted = _vnc_des_encrypt(password)
        _old_mask = os.umask(0o077)
        try:
            fd, path = tempfile.mkstemp(suffix='.vnc', prefix='pymrng_')
        finally:
            os.umask(_old_mask)
        try:
            os.write(fd, encrypted)
        finally:
            os.close(fd)
        if os.name == 'nt':
            from core.crypto import _restrict_file_permissions
            _restrict_file_permissions(path)
        return path
    except Exception:
        return ""


def _schedule_delete(path: str, delay: float = 3.0):
    """Cancella il file `path` dopo `delay` secondi in un thread daemon."""
    def _do():
        time.sleep(delay)
        try:
            os.unlink(path)
        except Exception:
            pass
    threading.Thread(target=_do, daemon=True).start()


# ── Protocollo VNC ────────────────────────────────────────────────────────────

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
            hostname = (info.hostname or "").strip()
            if not hostname or not _HOSTNAME_RE.match(hostname):
                self._label.setText("Hostname VNC non valido.")
                return False
            from core.crypto import decrypt
            password = decrypt(info.password) if info.password else ""
            cmd = [viewer, f"{hostname}::{info.port}"]

            # Passa password via file temporaneo (0600) invece di cmdline (VULN-15)
            pw_file = ""
            if password and ("tigervnc" in viewer.lower() or "tvnc" in viewer.lower()):
                pw_file = _write_vnc_password_file(password)
                if pw_file:
                    cmd += ["-passwd", pw_file]

            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            self._process = subprocess.Popen(
                cmd,
                creationflags=flags,
                close_fds=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )

            # Cancella il file password dopo che il viewer lo ha letto
            if pw_file:
                _schedule_delete(pw_file, delay=3.0)

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
