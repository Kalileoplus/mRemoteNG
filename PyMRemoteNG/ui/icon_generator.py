"""
Genera l'icona dell'applicazione: terminale con fulmine verde su sfondo nero.
"""
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QPen, QBrush, QPainterPath
from PyQt6.QtCore import Qt, QRect, QPoint, QSize
import os


def create_app_icon(size: int = 256) -> QIcon:
    """Crea l'icona dell'app: schermo terminale con prompt verde."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    p = QPainter(pixmap)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    s = size
    m = s // 16  # margin

    # ── Sfondo schermo (arrotondato) ──
    p.setBrush(QBrush(QColor("#0D0D0D")))
    p.setPen(QPen(QColor("#1E4A6E"), max(1, s // 32)))
    p.drawRoundedRect(m, m, s - 2*m, s - 2*m, s // 8, s // 8)

    # ── Barra titolo terminale ──
    bar_h = s // 10
    p.setBrush(QBrush(QColor("#1A3A5C")))
    p.setPen(Qt.PenStyle.NoPen)
    path = QPainterPath()
    r = s // 8
    path.addRoundedRect(m, m, s - 2*m, bar_h + r, r, r)
    p.fillPath(path, QColor("#1A3A5C"))
    p.fillRect(m, m + r, s - 2*m, bar_h, QColor("#1A3A5C"))

    # ── Pallini stile macOS nella barra ──
    dot_y = m + bar_h // 2
    dot_r = max(2, s // 28)
    colors = ["#FF5F57", "#FEBC2E", "#28C840"]
    for i, c in enumerate(colors):
        x = m + s // 14 + i * (dot_r * 3)
        p.setBrush(QBrush(QColor(c)))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(QPoint(x, dot_y), dot_r, dot_r)

    # ── Testo terminale ──
    font_size = max(8, s // 9)
    p.setFont(QFont("Consolas", font_size, QFont.Weight.Bold))

    # Linea 1: prompt verde
    p.setPen(QPen(QColor("#4EC94E")))
    line1_y = m + bar_h + s // 5
    p.drawText(m + s//12, line1_y, "user@srv:~$")

    # Linea 2: comando bianco
    p.setFont(QFont("Consolas", max(6, s // 12)))
    p.setPen(QPen(QColor("#D4D4D4")))
    p.drawText(m + s//12, line1_y + s//6, "ssh 172.16.0.1")

    # Linea 3: output grigio
    p.setPen(QPen(QColor("#555555")))
    p.drawText(m + s//12, line1_y + s//6*2, "Connected!")

    # ── Cursore lampeggiante ──
    cursor_w = max(3, s // 20)
    cursor_h = max(4, s // 14)
    cursor_x = m + s//12 + cursor_w * 8
    cursor_y = line1_y + s//6*2 + s//28
    p.setBrush(QBrush(QColor("#4EC94E")))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawRect(cursor_x, cursor_y - cursor_h, cursor_w, cursor_h)

    # ── Bordo glow ──
    p.setBrush(Qt.BrushStyle.NoBrush)
    pen_glow = QPen(QColor("#007ACC"))
    pen_glow.setWidth(max(1, s // 64))
    p.setPen(pen_glow)
    p.drawRoundedRect(m + 1, m + 1, s - 2*m - 2, s - 2*m - 2, s // 8, s // 8)

    p.end()
    return QIcon(pixmap)


def save_icon_file(path: str = "app_icon.ico"):
    """Salva l'icona come file .ico."""
    try:
        icon = create_app_icon(256)
        pixmap = icon.pixmap(QSize(256, 256))
        pixmap.save(path, "ICO")
        return True
    except Exception:
        return False
