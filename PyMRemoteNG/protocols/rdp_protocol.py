"""
Protocollo RDP — porta esatta di rdp_engine.py in PyQt6.

Logica identica a rdp_engine.py (che funziona):
  1. cmdkey per pre-salvare le credenziali
  2. Crea file .rdp temporaneo
  3. Avvia mstsc.exe normalmente
  4. Cerca TscShellContainerClass con FindWindowW (ogni 0.2s, timeout 15s)
  5. _attach_window: rimuove decorazioni + SetParent + SetWindowPos + RedrawWindow
  6. Resize: MoveWindow + SetWindowPos + RedrawWindow

Unica differenza da rdp_engine.py:
  - container = QWidget con WA_NativeWindow + paintEvent vuoto
    (equivalente del tkinter Canvas)
  - winId() al posto di winfo_id()
  - QThread al posto di threading.Thread
"""
from __future__ import annotations
import ctypes
import os
import subprocess
import tempfile
import time
from typing import TYPE_CHECKING, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QSizePolicy, QApplication
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtGui import QFont

from protocols.base import ProtocolBase
from themes.dark_theme import TEXT_COLOR, SUB_COLOR

if TYPE_CHECKING:
    from core.models import ConnectionInfo

# ── Win32 API — identico a rdp_engine.py ────────────────────────────────────
_u32 = ctypes.windll.user32

SetParent      = _u32.SetParent
SetWindowLong  = _u32.SetWindowLongW
GetWindowLong  = _u32.GetWindowLongW
MoveWindow     = _u32.MoveWindow
SetWindowPos   = _u32.SetWindowPos
RedrawWindow   = _u32.RedrawWindow
FindWindowW    = _u32.FindWindowW
FindWindowW.restype = ctypes.c_void_p

GWL_STYLE      = -16
WS_CHILD       = 0x40000000
WS_VISIBLE     = 0x10000000
WS_CAPTION     = 0x00C00000
WS_THICKFRAME  = 0x00040000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000
WS_SYSMENU     = 0x00080000
SWP_NOMOVE      = 0x0002
SWP_NOSIZE      = 0x0001
SWP_NOZORDER    = 0x0004
SWP_SHOWWINDOW  = 0x0040
SWP_FRAMECHANGED = 0x0020


def _attach_window(hwnd: int, parent_hwnd: int):
    """Identico a rdp_engine._attach_window."""
    try:
        cur = GetWindowLong(hwnd, GWL_STYLE)
        new = cur & ~(WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU)
        new |= WS_CHILD | WS_VISIBLE
        SetWindowLong(hwnd, GWL_STYLE, new)
        SetParent(hwnd, parent_hwnd)
        SetWindowPos(hwnd, 0, 0, 0, 0, 0,
                     SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED | SWP_SHOWWINDOW)
        RedrawWindow(hwnd, None, None, 0x85)
    except Exception:
        pass


def _resize_window(hwnd: int, w: int, h: int):
    """Identico a rdp_engine._resize_window."""
    if not hwnd:
        return
    w, h = max(1, w), max(1, h)
    MoveWindow(hwnd, 0, 0, w, h, True)
    SetWindowPos(hwnd, 0, 0, 0, w, h, SWP_NOZORDER | SWP_SHOWWINDOW)
    RedrawWindow(hwnd, None, None, 0x85)


# ── Container Qt — equivalente del tkinter Canvas ────────────────────────────

class _NativeCanvas(QWidget):
    """
    QWidget con HWND nativo reale e paintEvent vuoto.
    Equivalente esatto del tkinter.Canvas usato in rdp_engine.py.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._child_hwnd: int = 0

        # Attributi critici: HWND nativo + nessun background Qt
        self.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)
        self.setAttribute(Qt.WidgetAttribute.WA_PaintOnScreen, True)
        self.setMinimumSize(400, 300)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Forza la creazione dell'HWND immediatamente
        _ = int(self.winId())

    def paintEvent(self, event):
        # Non dipingere nulla: la finestra mstsc embedded si disegna da sola
        pass

    def get_hwnd(self) -> int:
        return int(self.winId())

    def embed(self, hwnd: int):
        self._child_hwnd = hwnd
        parent_hwnd = self.get_hwnd()
        _attach_window(hwnd, parent_hwnd)
        # Resize immediato + ritardato (come rdp_engine.py usa app.after)
        _resize_window(hwnd, self.width(), self.height())
        QTimer.singleShot(200, self._do_resize)
        QTimer.singleShot(600, self._do_resize)

    def _do_resize(self):
        if self._child_hwnd:
            _resize_window(self._child_hwnd, self.width(), self.height())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self._child_hwnd:
            _resize_window(self._child_hwnd, self.width(), self.height())

    def detach_child(self):
        if self._child_hwnd:
            try:
                SetParent(self._child_hwnd, 0)
            except Exception:
                pass
        self._child_hwnd = 0


# ── Thread RDP — equivalente di threading.Thread in rdp_engine.py ────────────

class _RDPThread(QThread):
    attached = pyqtSignal(int)   # hwnd trovato
    failed   = pyqtSignal(str)   # messaggio errore

    def __init__(self, rdp_file: str, timeout: float = 15.0):
        super().__init__()
        self._rdp_file = rdp_file
        self._timeout  = timeout
        self._proc: Optional[subprocess.Popen] = None

    def run(self):
        # Avvia mstsc — identico a rdp_engine.py: Popen semplice
        try:
            self._proc = subprocess.Popen(["mstsc", self._rdp_file])
        except Exception as e:
            self.failed.emit(f"mstsc.exe non trovato: {e}")
            return

        # Cerca TscShellContainerClass — identico a rdp_engine.py
        hwnd = None
        start = time.time()
        while time.time() - start < self._timeout:
            time.sleep(0.2)
            h = FindWindowW("TscShellContainerClass", None)
            if h:
                hwnd = int(h)
                break

        if hwnd:
            self.attached.emit(hwnd)
        else:
            self.failed.emit("Impossibile agganciare la finestra RDP.\n"
                             "Controlla host, credenziali e porta 3389.")

    def kill(self):
        if self._proc:
            try:
                self._proc.terminate()
            except Exception:
                pass


# ── Status widget ─────────────────────────────────────────────────────────────

class _StatusWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:#0A0A0A;")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        ly = QVBoxLayout(self)
        ly.setAlignment(Qt.AlignmentFlag.AlignCenter)

        ico = QLabel("🖥")
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setFont(QFont("Segoe UI Emoji", 28))
        ico.setStyleSheet("background:transparent; color:#2980B9;")
        ly.addWidget(ico)

        self._lbl = QLabel("Inizializzazione sessione RDP...")
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl.setWordWrap(True)
        self._lbl.setFont(QFont("Segoe UI", 11))
        self._lbl.setStyleSheet(f"color:{TEXT_COLOR}; background:transparent;")
        ly.addWidget(self._lbl)

        self._sub = QLabel("")
        self._sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub.setWordWrap(True)
        self._sub.setFont(QFont("Segoe UI", 9))
        self._sub.setStyleSheet(f"color:{SUB_COLOR}; background:transparent;")
        ly.addWidget(self._sub)

    def set(self, main: str, sub: str = "", color: str = TEXT_COLOR):
        self._lbl.setText(main)
        self._lbl.setStyleSheet(f"color:{color}; background:transparent;")
        self._sub.setText(sub)


# ── Credential helper — identico a rdp_engine._store_rdp_credentials ──────────

def _store_credentials(host: str, user: str, password: str):
    if not user or not password:
        return
    try:
        subprocess.run(
            ["cmdkey",
             f"/generic:TERMSRV/{host}",
             f"/user:{user}",
             f"/pass:{password}"],
            shell=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except Exception:
        pass


def _delete_credentials(host: str):
    try:
        subprocess.run(
            ["cmdkey", f"/delete:TERMSRV/{host}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except Exception:
        pass


# ── Protocollo principale ─────────────────────────────────────────────────────

class RDPProtocol(ProtocolBase):

    def __init__(self, connection_info: 'ConnectionInfo', parent_widget: QWidget):
        super().__init__(connection_info, parent_widget)
        self._username  = connection_info.username
        self._password  = ""
        self._domain    = getattr(connection_info, "domain", "")
        self._rdp_file  = ""
        self._thread: Optional[_RDPThread] = None
        self._canvas: Optional[_NativeCanvas] = None

        self._status = _StatusWidget()
        self._outer  = QWidget()
        self._outer.setStyleSheet("background:#0A0A0A;")
        ly = QVBoxLayout(self._outer)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.addWidget(self._status)

    # ── connect ──────────────────────────────────────────────────────────────

    def connect(self) -> bool:
        info = self.connection_info

        # Credential picker
        from ui.dialogs.credential_picker_dialog import CredentialPickerDialog
        dlg = CredentialPickerDialog(info, self._outer)
        if dlg.exec() == 0:
            self._status.set("Connessione annullata.", "", SUB_COLOR)
            return False

        self._username = dlg.result_username
        self._password = dlg.result_password
        self._domain   = dlg.result_domain

        # Dimensioni sessione = schermo primario
        screen = QApplication.primaryScreen()
        geom   = screen.availableGeometry()
        w, h   = geom.width(), geom.height()

        # Salva credenziali (identico a rdp_engine._store_rdp_credentials)
        _store_credentials(info.hostname, self._username, self._password)

        # Crea file .rdp (identico a rdp_engine._create_rdp_file)
        self._rdp_file = self._make_rdp_file(info, w, h)
        if not self._rdp_file:
            self._status.set("Impossibile creare il file RDP.", "", "#E05252")
            return False

        self._status.set(
            f"Connessione a {info.hostname}:{info.port or 3389}...",
            "Attendere il caricamento della sessione.")

        # Thread di ricerca (identico a rdp_engine.threading.Thread)
        self._thread = _RDPThread(self._rdp_file, timeout=15.0)
        self._thread.attached.connect(self._on_attached)
        self._thread.failed.connect(self._on_failed)
        self._thread.start()
        self.on_connected()
        return True

    # ── callbacks ────────────────────────────────────────────────────────────

    def _on_attached(self, hwnd: int):
        """Identico a rdp_engine: rimuove label, mostra canvas, fa embed."""
        canvas = _NativeCanvas(self._outer)
        self._canvas = canvas

        layout = self._outer.layout()
        layout.removeWidget(self._status)
        self._status.setVisible(False)
        layout.addWidget(canvas)

        # Mostra il canvas e processa eventi per creare l'HWND nativo
        canvas.show()
        QApplication.processEvents()

        # Embed (identico a rdp_engine: after(200, resize))
        QTimer.singleShot(200, lambda: canvas.embed(hwnd))

    def _on_failed(self, msg: str):
        _delete_credentials(self.connection_info.hostname)
        self._status.set("Errore RDP:", msg, "#E05252")

    # ── disconnect ────────────────────────────────────────────────────────────

    def disconnect(self):
        _delete_credentials(self.connection_info.hostname)
        if self._canvas:
            self._canvas.detach_child()
        if self._thread:
            self._thread.kill()
            self._thread.wait(1000)
        if self._rdp_file and os.path.exists(self._rdp_file):
            try:
                os.remove(self._rdp_file)
            except Exception:
                pass
        self.on_disconnected()

    def get_widget(self) -> QWidget:
        return self._outer

    def send_special_keys(self, keys: str):
        pass

    # ── .rdp file — identico a rdp_engine._create_rdp_file ──────────────────

    def _make_rdp_file(self, info, w: int, h: int) -> str:
        from core.crypto import decrypt
        # Risolvi password
        if not self._password and info.password:
            self._password = decrypt(info.password)

        user_str = (f"{self._domain}\\{self._username}"
                    if self._domain else self._username)

        lines = [
            f"full address:s:{info.hostname}",
            "screen mode id:i:2",
            "displayconnectionbar:i:0",
            "smart sizing:i:1",
            "prompt for credentials:i:0",
            "promptcredentialonce:i:0",
            "authentication level:i:0",
            "enablecredsspsupport:i:1",
            "use multimon:i:0",
            f"desktopwidth:i:{w}",
            f"desktopheight:i:{h}",
            "session bpp:i:32",
        ]
        if user_str.strip():
            lines.append(f"username:s:{user_str}")

        try:
            fd, path = tempfile.mkstemp(suffix=".rdp", prefix="pymremote_")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
            return path
        except Exception:
            return ""
