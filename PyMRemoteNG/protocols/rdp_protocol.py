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
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QApplication
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

_ShowWindow = _u32.ShowWindow

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
SW_SHOW         = 5


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


def _release_window(hwnd: int, x: int = 120, y: int = 80,
                    w: int = 1280, h: int = 800):
    """Stacca hwnd dal parent Qt e ripristina le decorazioni della finestra."""
    try:
        cur = GetWindowLong(hwnd, GWL_STYLE)
        # Rimuovi WS_CHILD, ripristina decorazioni normali
        new = (cur & ~WS_CHILD) | (WS_CAPTION | WS_THICKFRAME |
               WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU | WS_VISIBLE)
        SetWindowLong(hwnd, GWL_STYLE, new)
        SetParent(hwnd, 0)
        SetWindowPos(hwnd, 0, x, y, w, h,
                     SWP_NOZORDER | SWP_FRAMECHANGED | SWP_SHOWWINDOW)
        _ShowWindow(hwnd, SW_SHOW)
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
            self._proc = subprocess.Popen(
                ["mstsc", self._rdp_file], creationflags=_NO_WIN
            )
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

_NO_WIN = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0


def _store_credentials(host: str, user: str, password: str):
    if not user or not password:
        return
    try:
        subprocess.run(
            ["cmdkey", f"/generic:TERMSRV/{host}",
             f"/user:{user}", f"/pass:{password}"],
            shell=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=_NO_WIN, timeout=5,
        )
    except Exception:
        pass


def _safe_remove(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def _delete_credentials(host: str):
    try:
        subprocess.run(
            ["cmdkey", f"/delete:TERMSRV/{host}"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=_NO_WIN, timeout=5,
        )
    except Exception:
        pass


# ── Protocollo principale ─────────────────────────────────────────────────────

class RDPProtocol(ProtocolBase):

    def __init__(self, connection_info: 'ConnectionInfo', parent_widget: QWidget):
        super().__init__(connection_info, parent_widget)
        self._username      = connection_info.username
        self._password      = ""
        self._domain        = getattr(connection_info, "domain", "")
        self._rdp_file      = ""
        self._rdp_opts      = None
        self._detached_hwnd = 0        # HWND quando la finestra è staccata
        self._thread: Optional[_RDPThread] = None
        self._canvas: Optional[_NativeCanvas] = None

        # ── Layout _outer ────────────────────────────────────────
        self._outer = QWidget()
        self._outer.setStyleSheet("background:#0A0A0A;")
        ly = QVBoxLayout(self._outer)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(0)

        # Toolbar attach/detach (nascosta finché non è connesso)
        self._rdp_bar = self._build_rdp_bar()
        self._rdp_bar.setVisible(False)
        ly.addWidget(self._rdp_bar)

        self._status = _StatusWidget()
        ly.addWidget(self._status)

        # Placeholder "finestra staccata"
        self._detached_label = self._build_detached_placeholder()
        self._detached_label.setVisible(False)
        ly.addWidget(self._detached_label)

    def _build_rdp_bar(self) -> QWidget:
        """Barra superiore con info connessione + bottoni Stacca/Aggancia."""
        bar = QWidget()
        bar.setFixedHeight(30)
        bar.setStyleSheet(
            "background:#0D1A2A; border-bottom:1px solid #1A3A5A;"
        )
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 0, 8, 0)
        lay.setSpacing(8)

        self._bar_icon = QLabel("🖥")
        self._bar_icon.setStyleSheet("background:transparent; font-size:13px;")
        lay.addWidget(self._bar_icon)

        self._bar_host = QLabel(self.connection_info.hostname)
        self._bar_host.setStyleSheet(
            "color:#4E9EEC; font-size:11px; font-weight:bold; background:transparent;"
        )
        lay.addWidget(self._bar_host)

        self._bar_status = QLabel("● Connesso")
        self._bar_status.setStyleSheet(
            "color:#4EC94E; font-size:10px; background:transparent;"
        )
        lay.addWidget(self._bar_status)
        lay.addStretch()

        # Pulsante Stacca
        self._detach_btn = QPushButton("⤢  Stacca finestra")
        self._detach_btn.setFixedHeight(22)
        self._detach_btn.setToolTip("Rendi la sessione RDP una finestra mobile indipendente")
        self._detach_btn.setStyleSheet("""
            QPushButton {
                background: #1A3A5A; color: #5BA8E5;
                border: 1px solid #2A5A8A; border-radius: 3px;
                padding: 0 10px; font-size: 11px;
            }
            QPushButton:hover { background: #0D5A9E; color: white; }
        """)
        self._detach_btn.clicked.connect(self._on_detach)
        lay.addWidget(self._detach_btn)

        # Pulsante Aggancia
        self._reattach_btn = QPushButton("⤡  Aggancia")
        self._reattach_btn.setFixedHeight(22)
        self._reattach_btn.setVisible(False)
        self._reattach_btn.setToolTip("Reinserisci la finestra RDP nel tab dell'app")
        self._reattach_btn.setStyleSheet("""
            QPushButton {
                background: #1A3A1A; color: #4EC94E;
                border: 1px solid #2A5A2A; border-radius: 3px;
                padding: 0 10px; font-size: 11px;
            }
            QPushButton:hover { background: #0D6E0D; color: white; }
        """)
        self._reattach_btn.clicked.connect(self._on_reattach)
        lay.addWidget(self._reattach_btn)

        return bar

    def _build_detached_placeholder(self) -> QWidget:
        """Widget mostrato al posto del canvas quando la finestra è staccata."""
        w = QWidget()
        w.setStyleSheet("background:#050D15;")
        vl = QVBoxLayout(w)
        vl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        ico = QLabel("⤢")
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setStyleSheet("font-size:40px; color:#1A3A5A; background:transparent;")
        vl.addWidget(ico)

        txt = QLabel("Sessione RDP in finestra separata")
        txt.setAlignment(Qt.AlignmentFlag.AlignCenter)
        txt.setStyleSheet(
            "color:#4E9EEC; font-size:14px; font-weight:bold; background:transparent;"
        )
        vl.addWidget(txt)

        sub = QLabel(
            "La finestra mstsc è mobile — puoi spostarla liberamente.\n"
            "Premi  ⤡ Aggancia  nella barra in alto per reinserirla qui."
        )
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setWordWrap(True)
        sub.setStyleSheet("color:#3A5A7A; font-size:11px; background:transparent;")
        vl.addWidget(sub)

        return w

    # ── connect ──────────────────────────────────────────────────────────────

    def connect(self) -> bool:
        info = self.connection_info

        # Dialogo pre-connessione: credenziali + redirect + display
        from ui.dialogs.rdp_connect_dialog import RDPConnectDialog
        dlg = RDPConnectDialog(info, self._outer)
        if dlg.exec() != RDPConnectDialog.DialogCode.Accepted:
            self._status.set("Connessione annullata.", "", SUB_COLOR)
            return False

        opts = dlg.result_opts
        self._username = opts.username
        self._password = opts.password
        self._domain   = opts.domain
        self._rdp_opts = opts

        # Risoluzione
        if opts.resolution == "fullscreen":
            screen = QApplication.primaryScreen()
            geom   = screen.availableGeometry()
            w, h   = geom.width(), geom.height()
        else:
            w, h = opts.width, opts.height

        # Salva credenziali in Windows Credential Manager
        _store_credentials(info.hostname, self._username, self._password)

        # Crea file .rdp con tutte le opzioni selezionate
        self._rdp_file = self._make_rdp_file(info, w, h, opts)
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
        """Rimuove il label di stato, mostra la toolbar e il canvas embedded."""
        self._status.setVisible(False)

        canvas = _NativeCanvas(self._outer)
        self._canvas = canvas
        self._outer.layout().addWidget(canvas)

        canvas.show()
        QApplication.processEvents()

        QTimer.singleShot(200, lambda: canvas.embed(hwnd))

        # Mostra la toolbar con i controlli attach/detach
        self._rdp_bar.setVisible(True)
        self._bar_host.setText(
            f"{self.connection_info.hostname}:{self.connection_info.port or 3389}"
        )

    # ── Detach / Reattach ─────────────────────────────────────────────────────

    def _on_detach(self):
        """Stacca la finestra mstsc dal tab e la rende mobile."""
        if not self._canvas or not self._canvas._child_hwnd:
            return

        hwnd = self._canvas._child_hwnd
        self._detached_hwnd = hwnd

        # Calcola posizione iniziale della finestra staccata (centro schermo)
        screen = QApplication.primaryScreen().availableGeometry()
        sw, sh = screen.width(), screen.height()
        win_w, win_h = min(1280, sw - 100), min(800, sh - 100)
        x = (sw - win_w) // 2
        y = (sh - win_h) // 2

        # Stacca e ripristina decorazioni Windows
        _release_window(hwnd, x, y, win_w, win_h)
        self._canvas._child_hwnd = 0     # il canvas non controlla più la finestra

        # Mostra placeholder e aggiorna toolbar
        self._canvas.setVisible(False)
        self._detached_label.setVisible(True)
        self._detach_btn.setVisible(False)
        self._reattach_btn.setVisible(True)
        self._bar_status.setText("⤢ In finestra separata")
        self._bar_status.setStyleSheet(
            "color:#FFC107; font-size:10px; background:transparent;"
        )

    def _on_reattach(self):
        """Reinserisce la finestra mstsc nel canvas del tab."""
        hwnd = self._detached_hwnd
        if not hwnd:
            return

        # Verifica che la finestra esista ancora
        import ctypes
        if not ctypes.windll.user32.IsWindow(hwnd):
            self._bar_status.setText("● Finestra chiusa")
            self._bar_status.setStyleSheet(
                "color:#EF5350; font-size:10px; background:transparent;"
            )
            self._reattach_btn.setVisible(False)
            return

        self._detached_hwnd = 0

        # Nasconde placeholder, mostra canvas
        self._detached_label.setVisible(False)
        self._canvas.setVisible(True)

        # Re-embed
        self._canvas.embed(hwnd)

        # Aggiorna toolbar
        self._detach_btn.setVisible(True)
        self._reattach_btn.setVisible(False)
        self._bar_status.setText("● Connesso")
        self._bar_status.setStyleSheet(
            "color:#4EC94E; font-size:10px; background:transparent;"
        )

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
            self._thread.quit()
            self._thread.finished.connect(self._thread.deleteLater)
            self._thread = None
        rdp = self._rdp_file
        if rdp:
            # Elimina il file .rdp in background dopo 2s
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(2000, lambda: _safe_remove(rdp))
            self._rdp_file = ""
        self.on_disconnected()

    def get_widget(self) -> QWidget:
        return self._outer

    def send_special_keys(self, keys: str):
        pass

    # ── .rdp file — identico a rdp_engine._create_rdp_file ──────────────────

    def _make_rdp_file(self, info, w: int, h: int, opts=None) -> str:
        from core.crypto import decrypt
        if not self._password and info.password:
            self._password = decrypt(info.password)

        user_str = (f"{self._domain}\\{self._username}"
                    if self._domain else self._username)

        # Schermo intero vs finestra
        screen_mode = "2" if (opts is None or opts.resolution == "fullscreen") else "1"

        # NLA / livello autenticazione
        if opts and opts.use_nla:
            enablecredsspsupport = "1"
            auth_level = "0"
        else:
            enablecredsspsupport = "0"
            auth_level = "0"

        # Avvisi certificato
        disable_warn = "1" if (opts is None or opts.disable_warning) else "0"

        # Reindirizzamento
        redir_clipboard = "1" if (opts is None or opts.redirect_clipboard) else "0"
        redir_drives    = "DynamicDrives" if (opts and opts.redirect_drives) else "0"
        redir_printers  = "1" if (opts and opts.redirect_printers) else "0"
        redir_serial    = "1" if (opts and opts.redirect_serial) else "0"
        redir_smartcard = "1" if (opts and opts.redirect_smartcard) else "0"
        audio_mode      = "0" if (opts and opts.redirect_audio) else "2"  # 0=play here, 2=no play
        mic_mode        = "1" if (opts and opts.redirect_microphone) else "0"
        color_depth     = str(opts.color_depth) if opts else "32"

        lines = [
            f"full address:s:{info.hostname}",
            f"server port:i:{info.port or 3389}",
            f"screen mode id:i:{screen_mode}",
            f"desktopwidth:i:{w}",
            f"desktopheight:i:{h}",
            f"session bpp:i:{color_depth}",
            "displayconnectionbar:i:0",
            "smart sizing:i:1",
            "use multimon:i:0",
            # Credenziali
            "prompt for credentials:i:0",
            "promptcredentialonce:i:0",
            f"authentication level:i:{auth_level}",
            f"enablecredsspsupport:i:{enablecredsspsupport}",
            # Soppressione avvisi Windows
            f"gatewayusagemethod:i:0",
            f"gatewaycredentialssource:i:4",
            f"gatewayprofileusagemethod:i:0",
            # Reindirizzamento
            f"redirectclipboard:i:{redir_clipboard}",
            f"redirectdrives:i:{'1' if opts and opts.redirect_drives else '0'}",
            f"redirectprinters:i:{redir_printers}",
            f"redirectcomports:i:{redir_serial}",
            f"redirectsmartcards:i:{redir_smartcard}",
            f"audiomode:i:{audio_mode}",
            f"audiocapturemode:i:{mic_mode}",
            f"drivestoredirect:s:{redir_drives}",
            # Qualità
            "allow font smoothing:i:1",
            "allow desktop composition:i:1",
            "disable themes:i:0",
            "disable wallpaper:i:1",
            "disable full window drag:i:1",
            "disable menu anims:i:1",
            "disable cursor setting:i:0",
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
