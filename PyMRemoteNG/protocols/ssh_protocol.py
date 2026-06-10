"""
Protocollo SSH via paramiko.
Terminale VT100/xterm-256color con colori ANSI e pannello monitoraggio remoto.
"""
from __future__ import annotations
import re
import socket
import threading
import time
from typing import TYPE_CHECKING

import paramiko
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPlainTextEdit, QLabel,
    QPushButton, QSplitter, QFrame, QProgressBar, QSizePolicy,
    QScrollArea
)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QFont, QTextCursor, QColor, QTextCharFormat

from protocols.base import ProtocolBase
from themes.dark_theme import TEXT_COLOR, SUB_COLOR, ACCENT_COLOR

if TYPE_CHECKING:
    from core.models import ConnectionInfo

# ─────────────────────────────────────────────────────────
# Thread reader output SSH
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
# Colori ANSI
# ─────────────────────────────────────────────────────────
_DEFAULT_FG = "#CCCCCC"

_ANSI_COLORS = {
    30: "#4C4C4C", 31: "#C0392B", 32: "#27AE60", 33: "#D4A017",
    34: "#2980B9", 35: "#8E44AD", 36: "#16A085", 37: "#CCCCCC",
    90: "#888888", 91: "#E74C3C", 92: "#2ECC71", 93: "#F1C40F",
    94: "#5DADE2", 95: "#AF7AC5", 96: "#48C9B0", 97: "#FFFFFF",
}
_BOLD_MAP = {30: 90, 31: 91, 32: 92, 33: 93, 34: 94, 35: 95, 36: 96, 37: 97}


# ─────────────────────────────────────────────────────────
# Terminale VT100/xterm-256color
# ─────────────────────────────────────────────────────────
class VT100Terminal(QPlainTextEdit):
    # Cattura: CSI (params + lettera), OSC, charset, keypad, cursore singolo
    _ANSI = re.compile(
        r'\x1b(?:'
        r'\[([0-9;?]*)([A-Za-z])'      # CSI — gruppo 1=params, 2=lettera
        r'|\][^\x07\x1b]*(?:\x07|\x1b\\)'  # OSC (title etc.)
        r'|[()][AB012]'                 # charset designation
        r'|[=>]'                        # keypad mode
        r'|[MNOABC-Z\\]'               # cursore/single-char ESC
        r')'
    )

    def __init__(self, parent=None):
        super().__init__(parent)
        self._channel: paramiko.Channel | None = None
        self._pending_login = False
        self._login_pw_mode = False
        self._login_cb      = None
        self._login_buf     = ""

        self._cur_parts: list[tuple[str, str]] = [("", _DEFAULT_FG)]
        self._cur_col  = 0
        self._cur_fg   = _DEFAULT_FG
        self._bold     = False
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

        self._flush_timer = QTimer(self)
        self._flush_timer.setInterval(80)
        self._flush_timer.timeout.connect(self._flush_line_buffer)
        self._flush_timer.start()

    def _avail_fonts(self):
        from PyQt6.QtGui import QFontDatabase
        return QFontDatabase.families()

    def process_ssh_data(self, data: bytes):
        try:
            text = data.decode("utf-8", errors="replace")
        except Exception:
            text = data.decode("latin-1", errors="replace")
        self._feed(text)

    def _feed(self, text: str):
        i = 0
        while i < len(text):
            ch = text[i]

            # ── Sequenze ESC ────────────────────────────────────────
            if ch == '\x1b':
                m = self._ANSI.match(text, i)
                if m:
                    params = m.group(1) or ""
                    letter = m.group(2) if m.lastindex and m.lastindex >= 2 else ""
                    self._handle_csi(params, letter)
                    i = m.end()
                    continue
                i += 1
                continue

            # ── Controllo ───────────────────────────────────────────
            if ch == '\r':
                if i + 1 < len(text) and text[i + 1] == '\n':
                    self._commit_line()
                    i += 2
                else:
                    # \r singolo: azzera la riga corrente (progress bar, ecc.)
                    self._cur_parts = [("", self._cur_fg)]
                    self._cur_col   = 0
                    # Sovrascrivi la riga parziale già disegnata
                    if self._partial_start is not None:
                        cursor = self.textCursor()
                        cursor.setPosition(self._partial_start)
                        cursor.movePosition(QTextCursor.MoveOperation.End,
                                            QTextCursor.MoveMode.KeepAnchor)
                        cursor.removeSelectedText()
                    i += 1
                continue

            if ch == '\n':
                self._commit_line()
                i += 1
                continue

            if ch == '\x08':
                # Backspace
                for j in range(len(self._cur_parts) - 1, -1, -1):
                    if self._cur_parts[j][0]:
                        t, c = self._cur_parts[j]
                        self._cur_parts[j] = (t[:-1], c)
                        if self._cur_col > 0:
                            self._cur_col -= 1
                        break
                i += 1
                continue

            if ch == '\x07':  # BEL — ignora
                i += 1
                continue

            if ord(ch) >= 32 or ch == '\t':
                self._add_char(ch)
            i += 1

    def _handle_csi(self, params: str, letter: str):
        """Interpreta la sequenza CSI già parsata."""
        if letter == "m":
            self._process_sgr(params)

        elif letter in ("H", "f"):
            # Cursor Position — nel nostro terminale "line-based" lo trattiamo
            # solo come clear-to-bottom quando arriva dopo ESC[2J
            pass

        elif letter == "J":
            # Erase Display
            p = params or "0"
            if p in ("2", "3"):
                # ESC[2J o ESC[3J: cancella tutto lo schermo
                self._flush_timer.stop()
                self.clear()
                self._partial_start = None
                self._cur_parts = [("", self._cur_fg)]
                self._cur_col   = 0
                self._flush_timer.start()

        elif letter == "K":
            # Erase Line
            p = params or "0"
            if p == "0":
                # Cancella da cursore a fine riga → azzera buffer corrente
                self._cur_parts = [("", self._cur_fg)]
                self._cur_col   = 0
                if self._partial_start is not None:
                    cursor = self.textCursor()
                    cursor.setPosition(self._partial_start)
                    cursor.movePosition(QTextCursor.MoveOperation.End,
                                        QTextCursor.MoveMode.KeepAnchor)
                    cursor.removeSelectedText()
            elif p == "2":
                # Cancella tutta la riga
                self._cur_parts = [("", self._cur_fg)]
                self._cur_col   = 0
                if self._partial_start is not None:
                    cursor = self.textCursor()
                    cursor.setPosition(self._partial_start)
                    cursor.movePosition(QTextCursor.MoveOperation.End,
                                        QTextCursor.MoveMode.KeepAnchor)
                    cursor.removeSelectedText()

        elif letter == "A":
            pass  # cursor up — non supportato nel terminale line-based
        elif letter == "B":
            pass  # cursor down
        elif letter == "C":
            pass  # cursor right
        elif letter == "D":
            pass  # cursor left
        # Altre sequenze CSI ignorate silenziosamente

    def _add_char(self, ch: str):
        if self._cur_parts and self._cur_parts[-1][1] == self._cur_fg:
            t, c = self._cur_parts[-1]
            self._cur_parts[-1] = (t + ch, c)
        else:
            self._cur_parts.append((ch, self._cur_fg))
        self._cur_col += 1

    def _process_sgr(self, params: str):
        if not params or params == "0":
            self._cur_fg = _DEFAULT_FG; self._bold = False; return
        parts = params.split(";")
        idx = 0
        while idx < len(parts):
            try:
                n = int(parts[idx])
            except ValueError:
                idx += 1; continue
            if n == 0:
                self._cur_fg = _DEFAULT_FG; self._bold = False
            elif n == 1:
                self._bold = True
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
            elif n == 38 and idx + 1 < len(parts):
                mode = int(parts[idx+1]) if parts[idx+1].isdigit() else 0
                if mode == 5 and idx + 2 < len(parts):
                    try: self._cur_fg = self._color256(int(parts[idx+2]))
                    except ValueError: pass
                    idx += 2
                elif mode == 2 and idx + 4 < len(parts):
                    try:
                        r, g, b = int(parts[idx+2]), int(parts[idx+3]), int(parts[idx+4])
                        self._cur_fg = f"#{r:02X}{g:02X}{b:02X}"
                    except (ValueError, IndexError): pass
                    idx += 4
            idx += 1

    @staticmethod
    def _color256(n: int) -> str:
        if n < 16:
            return _ANSI_COLORS.get(n + 30 if n < 8 else n + 82, _DEFAULT_FG)
        if n < 232:
            n -= 16; b = n % 6; g = (n // 6) % 6; r = n // 36
            return f"#{r*51:02X}{g*51:02X}{b*51:02X}"
        gray = (n - 232) * 10 + 8
        return f"#{gray:02X}{gray:02X}{gray:02X}"

    def _set_partial(self, finalize: bool = False):
        cursor = self.textCursor()
        if self._partial_start is None:
            cursor.movePosition(QTextCursor.MoveOperation.End)
            self._partial_start = cursor.position()
        else:
            doc_len = self.document().characterCount()
            pos = min(self._partial_start, max(0, doc_len - 1))
            cursor.setPosition(pos)
            cursor.movePosition(QTextCursor.MoveOperation.End,
                                QTextCursor.MoveMode.KeepAnchor)
        cursor.beginEditBlock()
        first = True
        for part_text, part_color in self._cur_parts:
            if not part_text and not first:
                continue
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(part_color))
            cursor.insertText(part_text, fmt)
            first = False
        if finalize:
            reset = QTextCharFormat()
            reset.setForeground(QColor(_DEFAULT_FG))
            cursor.insertText("\n", reset)
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

    def write_info(self, text: str):    self.write_system(text, "#888888")
    def write_success(self, text: str): self.write_system(text, "#4EC94E")
    def write_error(self, text: str):   self.write_system(text, "#F14C4C")

    def set_channel(self, channel: paramiko.Channel):
        self._channel = channel
        self._pending_login = False
        self._login_pw_mode = False
        self.setFocus()

    def set_login_mode(self, pending_username=False, pending_password=False, cb=None):
        self._pending_login = pending_username or pending_password
        self._login_pw_mode = pending_password
        self._login_cb      = cb
        self._login_buf     = ""

    def keyPressEvent(self, e):
        key  = e.key()
        mods = e.modifiers()
        text = e.text()
        if self._pending_login:
            self._handle_login_key(key, text); return
        if self._channel:
            self._handle_ssh_key(key, mods, text); return
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
            self.write_system("\n")
            val = self._login_buf
            self._pending_login = False
            self._login_buf     = ""
            cb = self._login_cb; self._login_cb = None
            if cb: cb(val)
        elif key == Qt.Key.Key_Backspace:
            if self._login_buf:
                self._login_buf = self._login_buf[:-1]
                if not self._login_pw_mode:
                    self.textCursor().deletePreviousChar()
        elif text and text.isprintable():
            self._login_buf += text
            if not self._login_pw_mode:
                self.write_system(text)

    def _send(self, data: bytes):
        if self._channel:
            try: self._channel.send(data)
            except Exception: pass

    def send_text(self, text: str): self._send(text.encode("utf-8"))

    def mousePressEvent(self, e):
        super().mousePressEvent(e)
        self.setFocus()

    def cleanup(self):
        self._flush_timer.stop()
        if self._channel:
            try: self._channel.close()
            except Exception: pass


# ─────────────────────────────────────────────────────────
# Container widget terminale
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
            self._reader.quit()
            self._reader.finished.connect(self._reader.deleteLater)
        self.term.cleanup()


# ─────────────────────────────────────────────────────────
# Monitoring remoto — comando bash completo
# Raccoglie: CPU (2 letture /proc/stat), RAM (/proc/meminfo),
# Rete (2 letture /proc/net/dev), Uptime, User, tutte le partizioni
# ─────────────────────────────────────────────────────────
_MONITOR_CMD = (
    # Interfaccia di rete di default
    "iface=$(ip route 2>/dev/null | awk '/^default/{print $5; exit}');"
    "[ -z \"$iface\" ] && iface=$(awk 'NR>2{gsub(/:/,\"\",$1);"
    " if($1!=\"lo\"){print $1; exit}}' /proc/net/dev 2>/dev/null);"
    # Prima lettura CPU e rete (awk -v è più robusto di grep sul formato di /proc/net/dev)
    "c1=$(awk 'NR==1{$1=\"\"; print}' /proc/stat 2>/dev/null);"
    "rx1=$(awk -v i=\"${iface}:\" '$1==i{print $2}' /proc/net/dev 2>/dev/null);"
    "tx1=$(awk -v i=\"${iface}:\" '$1==i{print $10}' /proc/net/dev 2>/dev/null);"
    "sleep 0.5;"
    # Seconda lettura
    "c2=$(awk 'NR==1{$1=\"\"; print}' /proc/stat 2>/dev/null);"
    "rx2=$(awk -v i=\"${iface}:\" '$1==i{print $2}' /proc/net/dev 2>/dev/null);"
    "tx2=$(awk -v i=\"${iface}:\" '$1==i{print $10}' /proc/net/dev 2>/dev/null);"
    # CPU%: confronta le due letture di /proc/stat
    "printf '%s\\n%s\\n' \"$c1\" \"$c2\" | awk '"
    "NR==1{for(i=1;i<=NF;i++){t1+=$i; if(i==4)idle1=$i}}"
    "NR==2{for(i=1;i<=NF;i++){t2+=$i; if(i==4)idle2=$i}}"
    "END{dt=t2-t1; printf \"CPU %d\\n\", dt>0?100*(dt-(idle2-idle1))/dt:0}';"
    # Rete Mb/s (bytes delta * 8 / 0.5s / 1e6)
    "[ -n \"$rx1\" ] && [ -n \"$rx2\" ] && "
    "awk \"BEGIN{printf \\\"NET %.2f %.2f\\\\n\\\","
    "($rx2-$rx1)*8/0.5/1000000,($tx2-$tx1)*8/0.5/1000000}\" 2>/dev/null"
    " || echo 'NET 0.00 0.00';"
    # RAM in kB
    "awk '/MemTotal/{t=$2}/MemAvailable/{a=$2}"
    "END{printf \"MEM %d %d\\n\",t-a,t}' /proc/meminfo 2>/dev/null;"
    # Uptime in secondi
    "awk 'NR==1{printf \"UP %.0f\\n\",$1}' /proc/uptime 2>/dev/null;"
    # Utente corrente
    "echo \"USER $(id -un 2>/dev/null || echo unknown)\";"
    # Tutte le partizioni reali — esclude filesystem virtuali e /run,/sys,/proc,/snap
    "df -h 2>/dev/null | awk 'NR>1 && $1~/^\\// "
    "&& $1!~/^(tmpfs|devtmpfs|udev|overlay|shm|cgroupfs)$/ "
    "&& $NF!~/^\\/run|\\/sys|\\/proc|\\/dev\\/pts|\\/snap/ "
    "{printf \"DISK %s %s %s %s\\n\",$3,$2,$(NF-1),$NF}'"
)

_MONITOR_INTERVAL_S = 15


class _MonitorWorker(QThread):
    stats_ready = pyqtSignal(dict)

    def __init__(self, transport: paramiko.Transport):
        super().__init__()
        self._transport = transport
        self._running   = True

    def run(self):
        self._collect()
        while self._running:
            for _ in range(_MONITOR_INTERVAL_S * 10):
                if not self._running:
                    return
                self.msleep(100)
            self._collect()

    def _collect(self):
        try:
            if not (self._transport and self._transport.is_active()):
                return
            sess = self._transport.open_session()
            sess.exec_command(_MONITOR_CMD)
            sess.settimeout(8.0)
            data = b""
            deadline = time.time() + 8.0
            while time.time() < deadline:
                if sess.recv_ready():
                    chunk = sess.recv(8192)
                    if not chunk:
                        break
                    data += chunk
                elif sess.exit_status_ready() and not sess.recv_ready():
                    break
                else:
                    time.sleep(0.05)
            sess.close()
            stats = _parse_monitor_output(data.decode("utf-8", errors="replace"))
            if stats:
                self.stats_ready.emit(stats)
        except Exception:
            pass

    def stop(self):
        self._running = False


def _parse_monitor_output(output: str) -> dict:
    result: dict = {"disks": []}
    for line in output.splitlines():
        p = line.strip().split()
        if not p:
            continue
        key = p[0]
        if key == "CPU" and len(p) >= 2:
            try: result["cpu_pct"] = int(p[1])
            except ValueError: pass
        elif key == "NET" and len(p) >= 3:
            try:
                result["net_tx"] = float(p[1])
                result["net_rx"] = float(p[2])
            except ValueError: pass
        elif key == "MEM" and len(p) >= 3:
            try:
                used_kb, total_kb = int(p[1]), int(p[2])
                result["mem_used_mb"]  = used_kb // 1024
                result["mem_total_mb"] = total_kb // 1024
                result["mem_pct"] = int(100 * used_kb / total_kb) if total_kb else 0
            except (ValueError, ZeroDivisionError): pass
        elif key == "UP" and len(p) >= 2:
            try: result["uptime_s"] = int(float(p[1]))
            except ValueError: pass
        elif key == "USER" and len(p) >= 2:
            result["user"] = p[1]
        elif key == "DISK" and len(p) >= 5:
            try:
                pct = int(p[3].rstrip('%'))
            except ValueError:
                pct = 0
            result["disks"].append({
                "used":  p[1],
                "total": p[2],
                "pct":   pct,
                "mount": p[4],
            })
    return result


# ─────────────────────────────────────────────────────────
# Helper widgets del pannello monitor
# ─────────────────────────────────────────────────────────

def _sep_line() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.Shape.HLine)
    f.setStyleSheet("border:none; border-top:1px solid #1E1E1E; margin:3px 0;")
    return f


def _bar(color: str) -> QProgressBar:
    pb = QProgressBar()
    pb.setRange(0, 100)
    pb.setValue(0)
    pb.setTextVisible(False)
    pb.setFixedHeight(6)
    pb.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
    pb.setStyleSheet(f"""
        QProgressBar {{
            background:#1C1C1C; border:none; border-radius:3px;
        }}
        QProgressBar::chunk {{
            background:{color}; border-radius:3px;
        }}
    """)
    return pb


def _bar_colored(pct: int) -> str:
    """Restituisce il colore della barra disco in base all'utilizzo."""
    if pct >= 90:
        return "#F14C4C"
    if pct >= 75:
        return "#F5A623"
    return "#4EC94E"


def _lbl(text: str, color: str = "#888888", size: int = 10,
         bold: bool = False) -> QLabel:
    w = QLabel(text)
    weight = "bold" if bold else "normal"
    w.setStyleSheet(
        f"color:{color}; font-size:{size}px; font-weight:{weight};"
        f" background:transparent;"
    )
    return w


# ─────────────────────────────────────────────────────────
# Pannello monitoraggio — stile identico a MobaXterm
# ─────────────────────────────────────────────────────────
class SSHMonitorPanel(QWidget):
    """
    Pannello laterale con statistiche del server remoto.
    Mostra: CPU%, RAM, Rete ↑↓, Uptime, Utente, tutte le partizioni disco.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(230)
        self.setStyleSheet(
            "background:#080808; border-left:1px solid #1E1E1E;"
        )
        self._worker: _MonitorWorker | None = None
        self._disk_rows: list[dict] = []   # lista di widget disco
        self._build_ui()

    def _build_ui(self):
        # Scroll area per contenuto variabile (molte partizioni)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("""
            QScrollArea { border:none; background:#080808; }
            QScrollBar:vertical {
                background:#0A0A0A; width:4px; margin:0;
            }
            QScrollBar::handle:vertical {
                background:#2A2A2A; border-radius:2px; min-height:20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height:0; }
        """)

        inner = QWidget()
        inner.setStyleSheet("background:#080808;")
        lay = QVBoxLayout(inner)
        lay.setContentsMargins(10, 10, 8, 10)
        lay.setSpacing(4)

        # ── Titolo ──────────────────────────────────────────────────
        title = _lbl("📊  Monitor", "#5BA8E5", 11, bold=True)
        lay.addWidget(title)
        lay.addWidget(_sep_line())

        # ── CPU ─────────────────────────────────────────────────────
        cpu_row = QHBoxLayout()
        cpu_row.setContentsMargins(0, 0, 0, 0)
        cpu_row.addWidget(_lbl("CPU", "#AAAAAA", 10))
        cpu_row.addStretch()
        self._cpu_pct_lbl = _lbl("--", "#CCCCCC", 10, bold=True)
        cpu_row.addWidget(self._cpu_pct_lbl)
        lay.addLayout(cpu_row)
        self._cpu_bar = _bar("#5BA8E5")
        lay.addWidget(self._cpu_bar)

        lay.addSpacing(4)

        # ── RAM ─────────────────────────────────────────────────────
        ram_row = QHBoxLayout()
        ram_row.setContentsMargins(0, 0, 0, 0)
        ram_row.addWidget(_lbl("RAM", "#AAAAAA", 10))
        ram_row.addStretch()
        self._mem_pct_lbl = _lbl("--", "#CCCCCC", 10, bold=True)
        ram_row.addWidget(self._mem_pct_lbl)
        lay.addLayout(ram_row)
        self._mem_bar = _bar("#7EC8E3")
        lay.addWidget(self._mem_bar)
        self._mem_info_lbl = _lbl("-- / --", "#555555", 9)
        lay.addWidget(self._mem_info_lbl)

        lay.addSpacing(4)

        # ── Rete ────────────────────────────────────────────────────
        lay.addWidget(_sep_line())
        self._net_tx_lbl = _lbl("↑  --.- Mb/s", "#F5A623", 10)
        self._net_rx_lbl = _lbl("↓  --.- Mb/s", "#4EC94E", 10)
        lay.addWidget(self._net_tx_lbl)
        lay.addWidget(self._net_rx_lbl)

        # ── Uptime + Utente ─────────────────────────────────────────
        lay.addWidget(_sep_line())
        self._uptime_lbl = _lbl("⏱  --", "#CCCCCC", 10)
        self._user_lbl   = _lbl("👤  --", "#CCCCCC", 10)
        lay.addWidget(self._uptime_lbl)
        lay.addWidget(self._user_lbl)

        # ── Dischi (sezione dinamica) ────────────────────────────────
        lay.addWidget(_sep_line())
        disk_hdr = _lbl("DISCO", "#AAAAAA", 10)
        lay.addWidget(disk_hdr)
        self._disk_container_lay = QVBoxLayout()
        self._disk_container_lay.setSpacing(5)
        self._disk_container_lay.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(self._disk_container_lay)

        # ── Timestamp aggiornamento ─────────────────────────────────
        lay.addSpacing(6)
        self._updated_lbl = _lbl("--", "#2A2A2A", 9)
        lay.addWidget(self._updated_lbl)

        lay.addStretch()
        scroll.setWidget(inner)

        outer_lay = QVBoxLayout(self)
        outer_lay.setContentsMargins(0, 0, 0, 0)
        outer_lay.addWidget(scroll)

    # ── Avvio/stop monitoraggio ──────────────────────────────────────

    def start_monitoring(self, transport: paramiko.Transport):
        self._worker = _MonitorWorker(transport)
        self._worker.stats_ready.connect(self._on_stats)
        self._worker.start()

    def stop_monitoring(self):
        if self._worker:
            self._worker.stop()
            self._worker.quit()
            self._worker.finished.connect(self._worker.deleteLater)
            self._worker = None

    # ── Aggiornamento UI ─────────────────────────────────────────────

    def _on_stats(self, stats: dict):
        from datetime import datetime

        # CPU
        if "cpu_pct" in stats:
            v = stats["cpu_pct"]
            self._cpu_bar.setValue(v)
            color = "#F14C4C" if v >= 90 else ("#F5A623" if v >= 70 else "#5BA8E5")
            self._cpu_bar.setStyleSheet(
                f"QProgressBar{{background:#1C1C1C;border:none;border-radius:3px;}}"
                f"QProgressBar::chunk{{background:{color};border-radius:3px;}}"
            )
            self._cpu_pct_lbl.setText(f"{v}%")

        # RAM
        if "mem_pct" in stats:
            v = stats["mem_pct"]
            self._mem_bar.setValue(v)
            used  = stats.get("mem_used_mb", 0)
            total = stats.get("mem_total_mb", 0)
            self._mem_pct_lbl.setText(f"{v}%")
            if total >= 1024:
                self._mem_info_lbl.setText(
                    f"{used/1024:.2f} / {total/1024:.2f} GB"
                )
            else:
                self._mem_info_lbl.setText(f"{used} / {total} MB")

        # Rete
        if "net_tx" in stats:
            self._net_tx_lbl.setText(f"↑  {stats['net_tx']:.2f} Mb/s")
        if "net_rx" in stats:
            self._net_rx_lbl.setText(f"↓  {stats['net_rx']:.2f} Mb/s")

        # Uptime
        if "uptime_s" in stats:
            s = stats["uptime_s"]
            d, rem = divmod(s, 86400)
            h, rem = divmod(rem, 3600)
            m = rem // 60
            if d > 0 and h == 0 and m == 0:
                txt = f"{d} {'day' if d==1 else 'days'}"
            elif d > 0:
                txt = f"{d}d {h}h {m}m"
            elif h > 0:
                txt = f"{h}h {m}m"
            else:
                txt = f"{m}m"
            self._uptime_lbl.setText(f"⏱  {txt}")

        # Utente
        if "user" in stats:
            self._user_lbl.setText(f"👤  {stats['user']}")

        # Dischi — ricostruisce la sezione dinamicamente se i mount cambiano
        disks = stats.get("disks", [])
        if disks:
            self._rebuild_disks(disks)

        self._updated_lbl.setText(
            f"Agg. {datetime.now().strftime('%H:%M:%S')}"
        )

    def _rebuild_disks(self, disks: list[dict]):
        # Cancella widget esistenti
        while self._disk_container_lay.count():
            item = self._disk_container_lay.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        for d in disks:
            pct   = d["pct"]
            mount = d["mount"]
            used  = d["used"]
            total = d["total"]
            color = _bar_colored(pct)

            # Riga header: mount + percentuale
            hdr = QHBoxLayout()
            hdr.setContentsMargins(0, 0, 0, 0)
            hdr.setSpacing(4)

            # Mount point (troncato se lungo)
            mp_lbl = _lbl(mount, "#CCCCCC", 10)
            mp_lbl.setMaximumWidth(120)
            hdr.addWidget(mp_lbl)
            hdr.addStretch()

            pct_text = f"{pct}%"
            warn = " ⚠" if pct >= 90 else ""
            pct_color = "#F14C4C" if pct >= 90 else ("#F5A623" if pct >= 75 else "#CCCCCC")
            pct_lbl = _lbl(f"{pct_text}{warn}", pct_color, 10, bold=(pct >= 75))
            hdr.addWidget(pct_lbl)

            hdr_widget = QWidget()
            hdr_widget.setStyleSheet("background:transparent;")
            hdr_widget.setLayout(hdr)
            self._disk_container_lay.addWidget(hdr_widget)

            # Barra
            pb = _bar(color)
            pb.setValue(pct)
            self._disk_container_lay.addWidget(pb)

            # Info: usato / totale
            info_lbl = _lbl(f"{used} / {total}", "#444444", 9)
            self._disk_container_lay.addWidget(info_lbl)


# ─────────────────────────────────────────────────────────
# Thread login SSH
# ─────────────────────────────────────────────────────────
class SSHLoginWorker(QThread):
    connected    = pyqtSignal(object, object)   # (channel, SSHClient)
    ask_username = pyqtSignal()
    ask_password = pyqtSignal(str)
    failed       = pyqtSignal(str)
    info_msg     = pyqtSignal(str)

    def __init__(self, hostname: str, port: int, username: str, password: str):
        super().__init__()
        hostname = hostname.strip()
        if "@" in hostname:
            user_part, hostname = hostname.rsplit("@", 1)
            if not username.strip():
                username = user_part
        self.hostname = self._norm(hostname)
        self.port     = port or 22
        self.username = username.strip()
        self.password = password
        self._uev = threading.Event()
        self._pev = threading.Event()
        self._uval = ""; self._pval = ""

    @staticmethod
    def _norm(h: str) -> str:
        return re.sub(r'\.{2,}', '.', h.strip()).rstrip('.')

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
                self.failed.emit(f"Timeout: {hostname}:{self.port} non raggiungibile\n"); return
            except ConnectionRefusedError:
                self.failed.emit(f"Rifiutata: {hostname}:{self.port}\n"); return

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
                    s2 = socket.create_connection((resolved, self.port), timeout=10) if att > 0 else sock
                    cli = paramiko.SSHClient()
                    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                    cli.connect(
                        hostname=hostname, sock=s2,
                        username=username, password=password or None,
                        timeout=10, look_for_keys=True, allow_agent=True,
                        auth_timeout=10
                    )
                    ch = cli.invoke_shell(term="xterm-256color", width=220, height=50)
                    self.connected.emit(ch, cli)
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
# Protocollo principale
# ─────────────────────────────────────────────────────────
class SSHProtocol(ProtocolBase):

    def __init__(self, connection_info: 'ConnectionInfo', parent_widget: QWidget):
        super().__init__(connection_info, parent_widget)
        self._client: paramiko.SSHClient | None = None
        self._worker: SSHLoginWorker | None = None

        # ── Outer container ──────────────────────────────────────────
        self._outer = QWidget()
        self._outer.setStyleSheet("background:#0C0C0C;")
        main_lay = QVBoxLayout(self._outer)
        main_lay.setContentsMargins(0, 0, 0, 0)
        main_lay.setSpacing(0)

        # ── SSH bar ──────────────────────────────────────────────────
        self._ssh_bar = self._build_ssh_bar()
        main_lay.addWidget(self._ssh_bar)

        # ── Splitter: terminale | monitor ───────────────────────────
        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setHandleWidth(1)
        self._splitter.setStyleSheet(
            "QSplitter::handle { background:#1A1A1A; }"
        )
        self._term_widget = TerminalWidget()
        self._splitter.addWidget(self._term_widget)

        self._monitor = SSHMonitorPanel()
        self._monitor.setVisible(False)
        self._splitter.addWidget(self._monitor)
        self._splitter.setCollapsible(0, False)
        self._splitter.setCollapsible(1, True)
        self._splitter.setSizes([9000, 230])

        main_lay.addWidget(self._splitter)

    def _build_ssh_bar(self) -> QWidget:
        bar = QWidget()
        bar.setFixedHeight(28)
        bar.setStyleSheet("background:#0D1A0D; border-bottom:1px solid #1A3A1A;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(10, 0, 8, 0)
        lay.setSpacing(8)

        ico = QLabel("🐧")
        ico.setStyleSheet("font-size:13px; background:transparent;")
        lay.addWidget(ico)

        self._bar_host = QLabel(self.connection_info.hostname or "SSH")
        self._bar_host.setStyleSheet(
            "color:#4EC94E; font-size:11px; font-weight:bold; background:transparent;"
        )
        lay.addWidget(self._bar_host)

        self._bar_status = QLabel("Connessione in corso...")
        self._bar_status.setStyleSheet(
            "color:#444; font-size:10px; background:transparent;"
        )
        lay.addWidget(self._bar_status)
        lay.addStretch()

        self._monitor_btn = QPushButton("📊  Monitor")
        self._monitor_btn.setFixedHeight(20)
        self._monitor_btn.setCheckable(True)
        self._monitor_btn.setEnabled(False)
        self._monitor_btn.setToolTip(
            "Mostra/nascondi il pannello di monitoraggio remoto\n"
            "Aggiornamento ogni 15 s — CPU, RAM, Rete, Disco, Uptime, Utente"
        )
        self._monitor_btn.setStyleSheet("""
            QPushButton {
                background:#1A2A1A; color:#4EC94E;
                border:1px solid #2A4A2A; border-radius:3px;
                padding:0 8px; font-size:10px;
            }
            QPushButton:checked { background:#2A4A2A; border-color:#4EC94E; }
            QPushButton:hover   { background:#233323; }
            QPushButton:disabled { color:#222; border-color:#1A2A1A; }
        """)
        self._monitor_btn.toggled.connect(self._on_monitor_toggled)
        lay.addWidget(self._monitor_btn)
        return bar

    def _on_monitor_toggled(self, checked: bool):
        self._monitor.setVisible(checked)
        if checked:
            total = self._splitter.width()
            self._splitter.setSizes([max(100, total - 230), 230])
        else:
            self._splitter.setSizes([9000, 0])

    # ── connect ──────────────────────────────────────────────────────

    def connect(self) -> bool:
        info = self.connection_info
        from ui.dialogs.auth_dialog import SSHAuthDialog
        dlg = SSHAuthDialog(info, self.parent_widget)
        if dlg.exec() != SSHAuthDialog.DialogCode.Accepted:
            self._term_widget.write_info("Connessione annullata.\n")
            return False

        username = dlg.result_username
        pw       = dlg.result_password

        self._worker = SSHLoginWorker(info.hostname, info.port or 22, username, pw)
        self._worker.connected.connect(self._on_connected)
        self._worker.ask_username.connect(self._ask_username)
        self._worker.ask_password.connect(self._ask_password)
        self._worker.failed.connect(self._on_failed)
        self._worker.info_msg.connect(self._term_widget.write_info)
        self._worker.start()
        return True

    def _on_connected(self, ch, cli: paramiko.SSHClient):
        self._client = cli

        self._term_widget.write_success("Connesso — digita direttamente qui sopra\n")
        self._term_widget.set_channel(ch)

        self._bar_status.setText("● Connesso")
        self._bar_status.setStyleSheet(
            "color:#4EC94E; font-size:10px; background:transparent;"
        )
        self._monitor_btn.setEnabled(True)

        transport = cli.get_transport()
        if transport and transport.is_active():
            self._monitor.start_monitoring(transport)

        self.on_connected()
        try:
            from core.session_logger import SessionLogger
            SessionLogger.get_instance().log(
                "CONNECT", self.connection_info.hostname,
                self.connection_info.protocol.value,
                f"user={self.connection_info.username}"
            )
        except Exception:
            pass

    def _ask_username(self):
        self._term_widget.write_info("login as: ")
        self._term_widget.set_login_mode(
            pending_username=True,
            cb=lambda v: self._worker.provide_username(v) if self._worker else None
        )

    def _ask_password(self, msg: str):
        self._term_widget.write_info(msg)
        self._term_widget.set_login_mode(
            pending_password=True,
            cb=lambda v: self._worker.provide_password(v) if self._worker else None
        )

    def _on_failed(self, msg: str):
        self._term_widget.write_error(msg)
        self._bar_status.setText("● Errore connessione")
        self._bar_status.setStyleSheet(
            "color:#F14C4C; font-size:10px; background:transparent;"
        )
        self.on_disconnected()
        try:
            from core.session_logger import SessionLogger
            SessionLogger.get_instance().log(
                "ERROR", self.connection_info.hostname,
                self.connection_info.protocol.value,
                msg.strip()
            )
        except Exception:
            pass

    def disconnect(self):
        try:
            from core.session_logger import SessionLogger
            SessionLogger.get_instance().log(
                "DISCONNECT", self.connection_info.hostname,
                self.connection_info.protocol.value
            )
        except Exception:
            pass
        self._monitor.stop_monitoring()
        if self._worker:
            self._worker.quit()
            self._worker.finished.connect(self._worker.deleteLater)
            self._worker = None
        self._term_widget.cleanup()
        if self._client:
            try: self._client.close()
            except Exception: pass
            self._client = None
        self.on_disconnected()

    def get_widget(self) -> QWidget:
        return self._outer

    def send_special_keys(self, keys: str):
        self._term_widget.send_text(keys)
