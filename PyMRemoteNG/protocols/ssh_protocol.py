"""
Protocollo SSH2 via paramiko.
Terminale con VT100 line-buffer: gestisce correttamente \r, \n, ANSI colori.
"""
from __future__ import annotations
import re
import socket
import threading
from typing import TYPE_CHECKING

import paramiko
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QPlainTextEdit, QLabel
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont, QTextCursor, QColor, QTextCharFormat

from protocols.base import ProtocolBase

if TYPE_CHECKING:
    from core.models import ConnectionInfo

# ─────────────────────────────────────────────────────────
# Thread reader
# ─────────────────────────────────────────────────────────
class SSHOutputReader(QThread):
    data_received   = pyqtSignal(bytes)
    connection_lost = pyqtSignal()

    def __init__(self, channel: paramiko.Channel):
        super().__init__()
        self.channel  = channel
        self._running = True

    def run(self):
        while self._running:
            try:
                if self.channel.recv_ready():
                    data = self.channel.recv(8192)
                    if data:
                        self.data_received.emit(data)
                elif self.channel.closed or self.channel.eof_received:
                    self.connection_lost.emit()
                    break
                else:
                    self.msleep(15)
            except Exception:
                self.connection_lost.emit()
                break

    def stop(self):
        self._running = False


# ─────────────────────────────────────────────────────────
# Colori ANSI standard (palette terminale dark)
# ─────────────────────────────────────────────────────────
_DEFAULT_FG = "#CCCCCC"

_ANSI_COLORS = {
    # Normali
    30: "#4C4C4C",  # black
    31: "#C0392B",  # red
    32: "#27AE60",  # green
    33: "#D4A017",  # yellow
    34: "#2980B9",  # blue
    35: "#8E44AD",  # magenta
    36: "#16A085",  # cyan
    37: "#CCCCCC",  # white
    # Bright
    90: "#888888",  # bright black
    91: "#E74C3C",  # bright red
    92: "#2ECC71",  # bright green
    93: "#F1C40F",  # bright yellow
    94: "#5DADE2",  # bright blue
    95: "#AF7AC5",  # bright magenta
    96: "#48C9B0",  # bright cyan
    97: "#FFFFFF",  # bright white
}
# Bold usa la versione bright della stessa famiglia
_BOLD_MAP = {30: 90, 31: 91, 32: 92, 33: 93, 34: 94, 35: 95, 36: 96, 37: 97}


# ─────────────────────────────────────────────────────────
# Terminale VT100 con line buffer e colori ANSI
# ─────────────────────────────────────────────────────────
class VT100Terminal(QPlainTextEdit):
    """
    Terminale che:
    - riceve bytes raw SSH (con ANSI/VT100)
    - mantiene un line buffer per gestire \r (overwrite)
    - aggiorna QPlainTextEdit solo su \n o flush
    - cattura la tastiera e manda direttamente al canale SSH
    - supporta input login (username/password)
    """

    # Regex per le sequenze ANSI (cattura SGR separatamente)
    _ANSI = re.compile(
        r'\x1b(?:'
        r'\[([0-9;?]*)([A-Za-z])'   # CSI — gruppo 1=params, gruppo 2=lettera
        r'|\][^\x07\x1b]*(?:\x07|\x1b\\)'  # OSC
        r'|[()][AB012]'              # charset
        r'|[=>]'                     # keypad
        r'|[MNOABC-Z]'               # cursor/single-char
        r')'
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self._channel: paramiko.Channel | None = None
        self._pending_login = False
        self._login_pw_mode = False
        self._login_cb      = None
        self._login_buf     = ""

        # Line buffer colorato: lista di (testo, colore_hex)
        self._cur_parts: list[tuple[str, str]] = [("", _DEFAULT_FG)]
        self._cur_col  = 0
        self._cur_fg   = _DEFAULT_FG   # colore corrente
        self._bold     = False

        # Posizione nel documento dove inizia la riga parziale corrente.
        self._partial_start: int | None = None

        self.setReadOnly(False)
        self.setUndoRedoEnabled(False)
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)

        mono = next(
            (f for f in ("Cascadia Code", "Cascadia Mono", "Consolas", "Courier New")
             if f in self._avail_fonts()),
            "Courier New"
        )
        self.setFont(QFont(mono, 12))
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #0C0C0C;
                color: #CCCCCC;
                border: none;
                padding: 8px;
                selection-background-color: #264F78;
                selection-color: white;
            }
        """)
        self.setCursorWidth(10)

        # Flush periodico del line buffer (per prompt senza \n)
        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(80)
        self._flush_timer.timeout.connect(self._flush_line_buffer)
        self._flush_timer.start()

    def _avail_fonts(self):
        from PyQt6.QtGui import QFontDatabase
        return QFontDatabase.families()

    # ── Ricezione dati SSH ──

    def process_ssh_data(self, data: bytes):
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            text = data.decode("latin-1", errors="replace")
        self._feed(text)

    def _feed(self, text: str):
        """Processa il testo, interpreta sequenze ANSI colore e aggiorna il buffer."""
        i = 0
        while i < len(text):
            ch = text[i]

            # Sequenza ESC
            if ch == '\x1b':
                m = self._ANSI.match(text, i)
                if m:
                    params = m.group(1) or ""
                    letter = m.group(2) if m.lastindex and m.lastindex >= 2 else ""
                    if letter == "m":   # SGR → aggiorna colore
                        self._process_sgr(params)
                    i = m.end()
                    continue
                i += 1
                continue

            if ch == '\r':
                if i + 1 < len(text) and text[i + 1] == '\n':
                    self._commit_line()
                    i += 2
                else:
                    # \r solo: torna col 0, azzera la riga (progress bar)
                    self._cur_parts = [("", self._cur_fg)]
                    self._cur_col   = 0
                    i += 1
                continue

            if ch == '\n':
                self._commit_line()
                i += 1
                continue

            if ch == '\x08':
                # Backspace: rimuovi ultimo char dall'ultimo part non vuoto
                for j in range(len(self._cur_parts) - 1, -1, -1):
                    if self._cur_parts[j][0]:
                        t, c = self._cur_parts[j]
                        self._cur_parts[j] = (t[:-1], c)
                        if self._cur_col > 0:
                            self._cur_col -= 1
                        break
                i += 1
                continue

            if ord(ch) >= 32 or ch == '\t':
                self._add_char(ch)
            i += 1

    def _add_char(self, ch: str):
        """Aggiunge un carattere al buffer colorato corrente."""
        if self._cur_parts and self._cur_parts[-1][1] == self._cur_fg:
            t, c = self._cur_parts[-1]
            self._cur_parts[-1] = (t + ch, c)
        else:
            self._cur_parts.append((ch, self._cur_fg))
        self._cur_col += 1

    def _process_sgr(self, params: str):
        """Interpreta parametri SGR (Select Graphic Rendition) e aggiorna il colore."""
        if not params or params == "0":
            self._cur_fg = _DEFAULT_FG
            self._bold   = False
            return
        parts = params.split(";")
        idx = 0
        while idx < len(parts):
            try:
                n = int(parts[idx])
            except ValueError:
                idx += 1
                continue
            if n == 0:
                self._cur_fg = _DEFAULT_FG
                self._bold   = False
            elif n == 1:
                self._bold = True
                # Riapplica colore bright se era già un colore standard
                for code, color in _ANSI_COLORS.items():
                    if color == self._cur_fg and 30 <= code <= 37:
                        self._cur_fg = _ANSI_COLORS.get(_BOLD_MAP.get(code, code), color)
                        break
            elif n == 22:
                self._bold = False
            elif 30 <= n <= 37:
                base = _ANSI_COLORS[n]
                self._cur_fg = _ANSI_COLORS.get(_BOLD_MAP.get(n, n), base) if self._bold else base
            elif 90 <= n <= 97:
                self._cur_fg = _ANSI_COLORS[n]
            elif n == 39:
                self._cur_fg = _DEFAULT_FG
            elif n == 38:
                # Colore 256 (38;5;N) o truecolor (38;2;R;G;B)
                if idx + 1 < len(parts):
                    mode = int(parts[idx + 1]) if parts[idx + 1].isdigit() else 0
                    if mode == 5 and idx + 2 < len(parts):
                        try:
                            c256 = int(parts[idx + 2])
                            self._cur_fg = self._color256(c256)
                        except ValueError:
                            pass
                        idx += 2
                    elif mode == 2 and idx + 4 < len(parts):
                        try:
                            r, g, b = int(parts[idx+2]), int(parts[idx+3]), int(parts[idx+4])
                            self._cur_fg = f"#{r:02X}{g:02X}{b:02X}"
                        except (ValueError, IndexError):
                            pass
                        idx += 4
            idx += 1

    @staticmethod
    def _color256(n: int) -> str:
        """Converte indice 256-color → hex string."""
        if n < 16:
            return _ANSI_COLORS.get(n + 30 if n < 8 else n + 82, _DEFAULT_FG)
        if n < 232:
            n -= 16
            b = n % 6; g = (n // 6) % 6; r = n // 36
            return f"#{r*51:02X}{g*51:02X}{b*51:02X}"
        gray = (n - 232) * 10 + 8
        return f"#{gray:02X}{gray:02X}{gray:02X}"

    def _set_partial(self, finalize: bool = False):
        """
        Scrive/aggiorna la riga parziale nel documento con i colori corretti.
        Usa _partial_start per sovrascrivere sempre lo stesso punto — mai duplicati.
        """
        cursor = self.textCursor()
        if self._partial_start is None:
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self._partial_start = cursor.position()
        else:
            cursor.setPosition(self._partial_start)
            cursor.movePosition(QTextCursor.MoveOperation.End,
                                QTextCursor.MoveMode.KeepAnchor)

        cursor.beginEditBlock()
        first_insert = True
        for part_text, part_color in self._cur_parts:
            if not part_text and not first_insert:
                continue
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(part_color))
            cursor.insertText(part_text, fmt)
            first_insert = False
        if finalize:
            reset_fmt = QTextCharFormat()
            reset_fmt.setForeground(QColor(_DEFAULT_FG))
            cursor.insertText("\n", reset_fmt)
            self._partial_start = None
        cursor.endEditBlock()

        self.setTextCursor(cursor)
        self.ensureCursorVisible()

    def _commit_line(self):
        self._set_partial(finalize=True)
        self._cur_parts = [("", self._cur_fg)]
        self._cur_col   = 0

    def _flush_line_buffer(self):
        if not any(p[0] for p in self._cur_parts):
            return
        self._set_partial(finalize=False)

    # ── Messaggi di sistema (connessione, errori) ──

    def write_system(self, text: str, color: str = "#888888"):
        text = text.replace('\r\n', '\n').replace('\r', '\n')
        cursor = self.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        cursor.setCharFormat(fmt)
        cursor.insertText(text)
        reset = QTextCharFormat()
        reset.setForeground(QColor("#CCCCCC"))
        cursor.setCharFormat(reset)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        self._partial_start = None
        self._cur_parts = [("", self._cur_fg)]
        self._cur_col   = 0

    def write_info(self, text: str):
        self.write_system(text, "#888888")

    def write_success(self, text: str):
        self.write_system(text, "#4EC94E")

    def write_error(self, text: str):
        self.write_system(text, "#F14C4C")

    # ── Gestione canale SSH ──

    def set_channel(self, channel: paramiko.Channel):
        self._channel = channel
        self._pending_login = False
        self._login_pw_mode = False
        self.setFocus()

    def set_login_mode(self, pending_username=False, pending_password=False,
                       cb=None):
        self._pending_login = pending_username or pending_password
        self._login_pw_mode = pending_password
        self._login_cb      = cb
        self._login_buf     = ""

    # ── Input da tastiera ──

    def keyPressEvent(self, e):
        key  = e.key()
        mods = e.modifiers()
        text = e.text()

        if self._pending_login:
            self._handle_login_key(key, text)
            return

        if self._channel:
            self._handle_ssh_key(key, mods, text)
            return

        e.ignore()

    def _handle_ssh_key(self, key, mods, text):
        KEY_MAP = {
            Qt.Key.Key_Return:    b"\r",
            Qt.Key.Key_Enter:     b"\r",
            Qt.Key.Key_Backspace: b"\x7f",
            Qt.Key.Key_Delete:    b"\x1b[3~",
            Qt.Key.Key_Up:        b"\x1b[A",
            Qt.Key.Key_Down:      b"\x1b[B",
            Qt.Key.Key_Right:     b"\x1b[C",
            Qt.Key.Key_Left:      b"\x1b[D",
            Qt.Key.Key_Home:      b"\x1b[H",
            Qt.Key.Key_End:       b"\x1b[F",
            Qt.Key.Key_PageUp:    b"\x1b[5~",
            Qt.Key.Key_PageDown:  b"\x1b[6~",
            Qt.Key.Key_Tab:       b"\t",
            Qt.Key.Key_Escape:    b"\x1b",
            Qt.Key.Key_F1:  b"\x1bOP", Qt.Key.Key_F2:  b"\x1bOQ",
            Qt.Key.Key_F3:  b"\x1bOR", Qt.Key.Key_F4:  b"\x1bOS",
            Qt.Key.Key_F5:  b"\x1b[15~", Qt.Key.Key_F6: b"\x1b[17~",
            Qt.Key.Key_F7:  b"\x1b[18~", Qt.Key.Key_F8: b"\x1b[19~",
            Qt.Key.Key_F9:  b"\x1b[20~", Qt.Key.Key_F10: b"\x1b[21~",
            Qt.Key.Key_F11: b"\x1b[23~", Qt.Key.Key_F12: b"\x1b[24~",
        }
        if key in KEY_MAP:
            self._send(KEY_MAP[key])
        elif mods & Qt.KeyboardModifier.ControlModifier and text:
            self._send(bytes([ord(text) & 0x1F]))
        elif text:
            self._send(text.encode("utf-8", errors="replace"))

    def _handle_login_key(self, key, text):
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            if not self._login_pw_mode:
                self.write_system("\n")
            else:
                self.write_system("\n")  # no echo per password
            val = self._login_buf
            self._pending_login = False
            self._login_buf     = ""
            cb = self._login_cb
            self._login_cb      = None
            if cb:
                cb(val)
        elif key == Qt.Key.Key_Backspace:
            if self._login_buf:
                self._login_buf = self._login_buf[:-1]
                if not self._login_pw_mode:
                    # Cancella l'ultimo char dal terminale
                    cursor = self.textCursor()
                    cursor.deletePreviousChar()
        elif text and text.isprintable():
            self._login_buf += text
            if not self._login_pw_mode:
                self.write_system(text)
            # Password: nessun echo

    def _send(self, data: bytes):
        if self._channel:
            try:
                self._channel.send(data)
            except Exception:
                pass

    def send_text(self, text: str):
        self._send(text.encode("utf-8"))

    def mousePressEvent(self, e):
        super().mousePressEvent(e)
        self.setFocus()

    def cleanup(self):
        self._flush_timer.stop()
        if self._channel:
            try:
                self._channel.close()
            except Exception:
                pass


# ─────────────────────────────────────────────────────────
# Container widget SSH
# ─────────────────────────────────────────────────────────
class TerminalWidget(QWidget):
    def __init__(self):
        super().__init__()
        self._reader: SSHOutputReader | None = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self.term = VT100Terminal()
        layout.addWidget(self.term)

    def set_channel(self, channel: paramiko.Channel):
        self._reader = SSHOutputReader(channel)
        self._reader.data_received.connect(self.term.process_ssh_data)
        self._reader.connection_lost.connect(
            lambda: self.term.write_system("\n\n[Connessione chiusa]\n", "#F14C4C"))
        self._reader.start()
        self.term.set_channel(channel)

    def write_info(self, text: str):    self.term.write_info(text)
    def write_success(self, text: str): self.term.write_success(text)
    def write_error(self, text: str):   self.term.write_error(text)

    def set_login_mode(self, pending_username=False, pending_password=False, cb=None):
        self.term.set_login_mode(
            pending_username=pending_username,
            pending_password=pending_password,
            cb=cb
        )

    def send_text(self, text: str): self.term.send_text(text)

    def cleanup(self):
        if self._reader:
            self._reader.stop()
            self._reader.wait(1500)
        self.term.cleanup()


# ─────────────────────────────────────────────────────────
# Thread login SSH
# ─────────────────────────────────────────────────────────
class SSHLoginWorker(QThread):
    connected    = pyqtSignal(object)
    ask_username = pyqtSignal()
    ask_password = pyqtSignal(str)
    failed       = pyqtSignal(str)
    info_msg     = pyqtSignal(str)

    def __init__(self, hostname: str, port: int, username: str, password: str):
        super().__init__()
        self.hostname = self._norm(hostname)
        self.port     = port or 22
        self.username = username.strip()
        self.password = password
        self._uev = threading.Event()
        self._pev = threading.Event()
        self._uval = ""; self._pval = ""

    @staticmethod
    def _norm(h: str) -> str:
        h = h.strip()
        h = re.sub(r'\.{2,}', '.', h)
        return h.rstrip('.')

    def provide_username(self, v: str): self._uval = v; self._uev.set()
    def provide_password(self, v: str): self._pval = v; self._pev.set()

    def run(self):
        try:
            hostname = self.hostname
            is_ip    = bool(re.match(r'^\d{1,3}(\.\d{1,3}){3}$', hostname))
            try:
                resolved = hostname if is_ip else socket.gethostbyname(hostname)
            except socket.gaierror as e:
                self.failed.emit(f"DNS: impossibile risolvere '{hostname}': {e}\n")
                return

            self.info_msg.emit(f"Connessione a {hostname}:{self.port}...\n")
            try:
                sock = socket.create_connection((resolved, self.port), timeout=10)
            except socket.timeout:
                self.failed.emit(f"Timeout: {hostname}:{self.port} non raggiungibile\n")
                return
            except ConnectionRefusedError:
                self.failed.emit(f"Rifiutata: {hostname}:{self.port}\n")
                return

            username = self.username
            if not username:
                self.ask_username.emit()
                self._uev.wait(120); username = self._uval.strip()
                if not username:
                    self.failed.emit("Username non fornito.\n"); return

            password = self.password
            if not password:
                self.ask_password.emit(f"Password per {username}@{hostname}: ")
                self._pev.wait(120); password = self._pval; self._pval = ""

            self.info_msg.emit(f"Autenticazione come '{username}'...\n")
            max_att = 3
            for att in range(max_att):
                try:
                    s2  = socket.create_connection((resolved, self.port), timeout=10) if att > 0 else sock
                    cli = paramiko.SSHClient()
                    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    cli.connect(hostname=hostname, sock=s2, username=username,
                                password=password or None, timeout=10,
                                look_for_keys=True, allow_agent=True,
                                auth_timeout=10)
                    ch = cli.invoke_shell(term="xterm-256color", width=220, height=50)
                    self.connected.emit(ch)
                    return
                except paramiko.AuthenticationException:
                    if att < max_att - 1:
                        self.ask_password.emit(
                            f"\nPassword errata. Riprova ({att+2}/{max_att}): ")
                        self._pev.clear(); self._pev.wait(120)
                        password = self._pval; self._pval = ""
                    else:
                        self.failed.emit("Accesso negato: troppi tentativi.\n"); return
                except paramiko.SSHException as e:
                    self.failed.emit(f"Errore SSH: {e}\n"); return

        except Exception as e:
            self.failed.emit(f"Errore: {e}\n")


# ─────────────────────────────────────────────────────────
# Protocollo
# ─────────────────────────────────────────────────────────
class SSHProtocol(ProtocolBase):

    def __init__(self, connection_info: 'ConnectionInfo', parent_widget: QWidget):
        super().__init__(connection_info, parent_widget)
        self._widget = TerminalWidget()
        self._worker: SSHLoginWorker | None = None

    def connect(self) -> bool:
        info = self.connection_info
        from core.crypto import decrypt
        pw = decrypt(info.password) if info.password else ""
        self._worker = SSHLoginWorker(info.hostname, info.port or 22, info.username, pw)
        self._worker.connected.connect(self._on_connected)
        self._worker.ask_username.connect(self._ask_username)
        self._worker.ask_password.connect(self._ask_password)
        self._worker.failed.connect(self._on_failed)
        self._worker.info_msg.connect(self._widget.write_info)
        self._worker.start()
        return True

    def _on_connected(self, ch):
        self._widget.write_success("Connesso — digita direttamente qui sopra\n")
        self._widget.set_channel(ch)
        self.on_connected()

    def _ask_username(self):
        self._widget.write_info("login as: ")
        self._widget.set_login_mode(
            pending_username=True,
            cb=lambda v: self._worker.provide_username(v) if self._worker else None
        )

    def _ask_password(self, msg: str):
        self._widget.write_info(msg)
        self._widget.set_login_mode(
            pending_password=True,
            cb=lambda v: self._worker.provide_password(v) if self._worker else None
        )

    def _on_failed(self, msg: str):
        self._widget.write_error(msg)
        self.on_disconnected()

    def disconnect(self):
        if self._worker: self._worker.quit()
        self._widget.cleanup()
        self.on_disconnected()

    def get_widget(self) -> QWidget:
        return self._widget

    def send_special_keys(self, keys: str):
        self._widget.send_text(keys)
