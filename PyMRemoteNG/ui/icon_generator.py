"""
Icona Nexus: hub di connessioni con nodi irradianti.
Genera tutti i tagli dimensionali per taskbar, titolo e alt+tab.
"""
from __future__ import annotations
import math
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QPen, QBrush
from PyQt6.QtCore import Qt, QPoint, QRect, QSize

_BG      = "#0D1117"
_ACCENT  = "#007ACC"
_BORDER  = "#1E4A6E"
_NODE_BG = "#0F2A40"
_NODE_FG = "#5BA8E5"
_SPOKE   = "#1A3A5A"


def _draw(size: int) -> QPixmap:
    px = QPixmap(size, size)
    px.fill(Qt.GlobalColor.transparent)
    p  = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    s  = size
    cx = cy = s / 2
    m  = max(1, s // 14)

    # ── Sfondo ───────────────────────────────────────────────────
    p.setBrush(QBrush(QColor(_BG)))
    p.setPen(Qt.PenStyle.NoPen)
    radius = s // 5
    p.drawRoundedRect(int(m), int(m), s - 2*int(m), s - 2*int(m), radius, radius)

    if size >= 24:
        # ── Spoke lines ──────────────────────────────────────────
        spoke_len = s * 0.30
        pen = QPen(QColor(_SPOKE))
        pen.setWidth(max(1, s // 40))
        p.setPen(pen)
        angles = [45, 135, 225, 315]
        outer = []
        for ang in angles:
            rad = math.radians(ang)
            ox = cx + spoke_len * math.cos(rad)
            oy = cy + spoke_len * math.sin(rad)
            outer.append((ox, oy))
            p.drawLine(QPoint(int(cx), int(cy)), QPoint(int(ox), int(oy)))

        # ── Nodi esterni ─────────────────────────────────────────
        nr = max(2, s // 13)
        p.setPen(Qt.PenStyle.NoPen)
        for ox, oy in outer:
            # cerchio esterno
            p.setBrush(QBrush(QColor(_NODE_BG)))
            p.drawEllipse(QPoint(int(ox), int(oy)), nr, nr)
            # punto interno colorato
            inner = max(1, nr * 2 // 3)
            p.setBrush(QBrush(QColor(_NODE_FG)))
            p.drawEllipse(QPoint(int(ox), int(oy)), inner, inner)

    # ── Glow centrale ────────────────────────────────────────────
    if size >= 48:
        glow_r = s // 6
        glow   = QColor(0, 122, 204, 45)
        p.setBrush(QBrush(glow))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPoint(int(cx), int(cy)), glow_r, glow_r)

    # ── Hub centrale ─────────────────────────────────────────────
    hub_r = max(3, s // 8) if size >= 24 else max(3, s // 5)
    p.setBrush(QBrush(QColor(_ACCENT)))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPoint(int(cx), int(cy)), hub_r, hub_r)

    # ── "N" sull'hub (solo dimensioni medio-grandi) ──────────────
    if size >= 32:
        font_size = max(5, hub_r - 2)
        fnt = QFont("Segoe UI", font_size, QFont.Weight.Bold)
        p.setFont(fnt)
        p.setPen(QPen(QColor("white")))
        rect = QRect(int(cx - hub_r), int(cy - hub_r), hub_r * 2, hub_r * 2)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, "N")

    # ── Bordo esterno ────────────────────────────────────────────
    border_pen = QPen(QColor(_BORDER))
    border_pen.setWidth(max(1, s // 72))
    p.setPen(border_pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawRoundedRect(int(m), int(m), s - 2*int(m), s - 2*int(m), radius, radius)

    p.end()
    return px


def create_app_icon(size: int = 256) -> QIcon:
    """Crea un QIcon con tutti i tagli standard per taskbar e titolo."""
    icon = QIcon()
    for s in [16, 24, 32, 48, 64, 128, 256]:
        icon.addPixmap(_draw(s))
    return icon


def save_icon_file(path: str = "app_icon.ico") -> bool:
    """Salva l'icona come file .ico (usato da PyInstaller)."""
    try:
        px = _draw(256)
        px.save(path, "ICO")
        return True
    except Exception:
        return False
