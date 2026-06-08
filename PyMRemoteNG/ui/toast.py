"""
Sistema toast — notifiche non bloccanti angolo basso-destra.
Uso:
    ToastManager.get_instance().show("success", "Titolo", "Corpo")
    ToastManager.get_instance().show("error",   "Errore", "Dettaglio")
Livelli: success | info | warning | error
"""
from __future__ import annotations
from typing import List

from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPoint, QPropertyAnimation, QEasingCurve, QRect
from PyQt6.QtGui import QFont, QColor
from PyQt6.QtWidgets import (
    QFrame, QHBoxLayout, QVBoxLayout, QLabel, QPushButton, QWidget
)
from themes.dark_theme import SUB_COLOR

_W = 320
_H = 74
_MARGIN  = 14
_SPACING = 6

_CFG = {
    "success": ("✓", "#4EC94E", "#091409"),
    "info":    ("●", "#5BA8E5", "#091419"),
    "warning": ("⚠", "#FFC107", "#191200"),
    "error":   ("✕", "#EF5350", "#190909"),
}


class Toast(QFrame):
    """Singola notifica toast."""

    closed = pyqtSignal(object)   # emette sé stesso

    def __init__(self, parent: QWidget, level: str,
                 title: str, body: str, duration: int):
        super().__init__(parent)
        icon_ch, color, bg = _CFG.get(level, _CFG["info"])

        self.setFixedSize(_W, _H)
        self.setStyleSheet(f"""
            QFrame {{
                background:{bg};
                border:1px solid {color}44;
                border-left:4px solid {color};
                border-radius:6px;
            }}
        """)

        lay = QHBoxLayout(self)
        lay.setContentsMargins(12, 8, 8, 8)
        lay.setSpacing(10)

        # Icona
        ico = QLabel(icon_ch)
        ico.setFixedWidth(22)
        ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ico.setFont(QFont("Segoe UI Emoji", 14))
        ico.setStyleSheet(f"color:{color}; background:transparent; border:none;")
        lay.addWidget(ico)

        # Testo
        txt = QVBoxLayout()
        txt.setSpacing(2)
        t1 = QLabel(title)
        t1.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        t1.setStyleSheet(f"color:{color}; background:transparent; border:none;")
        txt.addWidget(t1)
        if body:
            t2 = QLabel(body[:90] + ("…" if len(body) > 90 else ""))
            t2.setFont(QFont("Segoe UI", 9))
            t2.setWordWrap(True)
            t2.setStyleSheet(f"color:{SUB_COLOR}; background:transparent; border:none;")
            txt.addWidget(t2)
        lay.addLayout(txt, 1)

        # Pulsante chiudi
        xb = QPushButton("✕")
        xb.setFixedSize(18, 18)
        xb.setStyleSheet(
            "QPushButton{background:transparent;color:#444;border:none;font-size:10px;}"
            f"QPushButton:hover{{color:{color};}}"
        )
        xb.clicked.connect(self._dismiss)
        lay.addWidget(xb, 0, Qt.AlignmentFlag.AlignTop)

        # Auto-dismiss
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._dismiss)
        self._timer.start(duration)

        self.raise_()
        self.show()

    def _dismiss(self):
        self._timer.stop()
        self.closed.emit(self)


class ToastManager:
    """
    Singleton — chiama `ToastManager.init(main_window)` all'avvio,
    poi `ToastManager.get_instance().show(...)` ovunque.
    """
    _instance: "ToastManager | None" = None
    _parent:   QWidget | None        = None
    _stack:    List[Toast]           = []

    @classmethod
    def init(cls, parent: QWidget):
        if cls._instance is None:
            cls._instance = cls()
        cls._instance._parent = parent
        cls._instance._stack  = []

    @classmethod
    def get_instance(cls) -> "ToastManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ── API pubblica ─────────────────────────────────────────────────────────

    def show(self, level: str, title: str, body: str = "",
             duration: int = 4500):
        """Mostra un toast. Thread-safe se chiamato dal main thread Qt."""
        if not self._parent:
            return
        t = Toast(self._parent, level, title, body, duration)
        t.closed.connect(self._on_closed)
        self._stack.append(t)
        self._restack()

    def restack(self):
        """Chiamare da resizeEvent del parent per riposizionare."""
        self._restack()

    # ── Internals ────────────────────────────────────────────────────────────

    def _on_closed(self, toast: Toast):
        if toast in self._stack:
            self._stack.remove(toast)
        toast.hide()
        toast.deleteLater()
        self._restack()

    def _restack(self):
        if not self._parent:
            return
        pw = self._parent.width()
        ph = self._parent.height()
        x  = pw - _W - _MARGIN
        y_bottom = ph - _MARGIN
        for toast in reversed(self._stack[-4:]):   # max 4 visibili
            y = y_bottom - _H
            toast.move(x, y)
            toast.raise_()
            y_bottom = y - _SPACING
