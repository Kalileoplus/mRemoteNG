"""
Pannello albero connessioni — stile MobaXterm.
Cartelle colorate per tipo, indicatori stato connessione,
gerarchia visuale con guide verticali e badge conteggio.
"""
from __future__ import annotations
import re
from typing import Dict, Optional, Set, TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QMenu, QLineEdit, QHBoxLayout, QLabel, QPushButton,
    QAbstractItemView, QStyledItemDelegate, QApplication, QStyle
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QSize, QRect, QRectF
from PyQt6.QtGui import (
    QFont, QAction, QColor, QPainter, QFontMetrics,
    QPen, QBrush, QPainterPath, QLinearGradient
)
from themes.dark_theme import ACCENT_COLOR, CARD_COLOR, TEXT_COLOR, SUB_COLOR, BG_COLOR

if TYPE_CHECKING:
    from core.models import ConnectionInfo, ContainerInfo, RootNode


# ─────────────────────────────────────────────────────────────
# Colori per protocollo
# ─────────────────────────────────────────────────────────────
PROTO_COLOR = {
    "SSH2": "#4EC94E", "SSH1": "#4EC94E",
    "RDP":  "#4E9EEC",
    "VNC":  "#EC8C4E", "ARD": "#EC8C4E",
    "HTTP": "#A78FEC", "HTTPS": "#A78FEC",
    "Telnet": "#E0C44E", "Rlogin": "#E0C44E", "RAW": "#888888",
}

PROTO_SHORT = {
    "SSH2": "SSH", "SSH1": "SSH1",
    "RDP": "RDP", "VNC": "VNC", "ARD": "ARD",
    "HTTP": "HTTP", "HTTPS": "TLS",
    "Telnet": "TEL", "Rlogin": "RLG", "RAW": "RAW",
}


def _folder_style(name: str) -> tuple[str, str, str]:
    """Ritorna (bg_color, icon_char, accent_color) in base al nome cartella."""
    n = name.lower()
    if any(k in n for k in ("server", "srv", "rack", "blade", "hypervisor", "vm")):
        return "#0D1F33", "⬛", "#5BA8E5"   # blu — sala server
    if any(k in n for k in ("sist", "admin", "network", "rete", "fw", "firewall", "switch", "router")):
        return "#1F1A00", "⬛", "#F5A623"   # arancio — sistemistica
    if any(k in n for k in ("prod", "production", "live", "prd")):
        return "#1F0A0A", "⬛", "#EF5350"   # rosso — produzione
    if any(k in n for k in ("dev", "test", "staging", "svilup", "lab", "sandbox")):
        return "#0A1F0A", "⬛", "#4EC94E"   # verde — dev/test
    if any(k in n for k in ("backup", "bck", "archive", "storage", "nas", "san")):
        return "#1A1A00", "⬛", "#FFC107"   # giallo — backup/storage
    if any(k in n for k in ("dmz", "external", "cloud", "azure", "aws", "gcp")):
        return "#001A1A", "⬛", "#26C9A8"   # teal — cloud/dmz
    if any(k in n for k in ("discover", "scan", "found")):
        return "#1A0F1A", "⬛", "#9B7FE8"   # viola — discovery
    return "#161616", "⬛", "#888888"        # grigio — default


# ─────────────────────────────────────────────────────────────
# Delegate
# ─────────────────────────────────────────────────────────────
class _ConnDelegate(QStyledItemDelegate):

    CONN_H = 46
    FOLD_H = 30
    ROOT_H = 32

    def __init__(self, parent=None):
        super().__init__(parent)
        self._connected_ids: Set[str] = set()
        self._ping_status: Dict[str, Optional[bool]] = {}

    def sizeHint(self, option, index):
        node = index.data(Qt.ItemDataRole.UserRole)
        from core.models import ConnectionInfo, RootNode
        if isinstance(node, RootNode):
            h = self.ROOT_H
        elif isinstance(node, ConnectionInfo) and not node.is_container:
            h = self.CONN_H
        else:
            h = self.FOLD_H
        return QSize(option.rect.width(), h)

    def paint(self, painter: QPainter, option, index):
        node = index.data(Qt.ItemDataRole.UserRole)
        from core.models import ConnectionInfo, ContainerInfo, RootNode
        if node is None:
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        r = option.rect
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered  = bool(option.state & QStyle.StateFlag.State_MouseOver)

        # ── ROOT ──
        if isinstance(node, RootNode):
            self._draw_root(painter, r, node, selected)
        # ── CARTELLA ──
        elif isinstance(node, ContainerInfo):
            depth = index.data(Qt.ItemDataRole.UserRole + 1) or 0
            self._draw_folder(painter, r, node, selected, hovered, depth)
        # ── CONNESSIONE ──
        else:
            self._draw_connection(painter, r, node, selected, hovered)

        painter.restore()

    # ── ROOT ──────────────────────────────────────────────────

    def _draw_root(self, painter, r, node, selected):
        bg = QColor(ACCENT_COLOR) if selected else QColor("#1A2A1A")
        painter.fillRect(r, bg)
        # Linea inferiore
        painter.setPen(QPen(QColor("#2A3A2A"), 1))
        painter.drawLine(r.left(), r.bottom(), r.right(), r.bottom())

        f = QFont("Segoe UI", 10, QFont.Weight.Bold)
        painter.setFont(f)
        painter.setPen(QColor("white") if selected else QColor(ACCENT_COLOR))
        text_r = QRect(r.left() + 10, r.top(), r.width() - 14, r.height())
        total = _count_connections(node)
        painter.drawText(text_r, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         f"Connessioni  [{total}]")

    # ── CARTELLA ──────────────────────────────────────────────

    def _draw_folder(self, painter, r, node, selected, hovered, depth):
        _, _, accent = _folder_style(node.name)
        accent_c = QColor(accent)

        if selected:
            bg = QColor(ACCENT_COLOR)
        elif hovered:
            bg = QColor(accent_c.red(), accent_c.green(), accent_c.blue(), 30)
        else:
            bg = QColor(BG_COLOR)
        painter.fillRect(r, bg)

        # Bordo sinistro colorato (4px)
        bar_w = 4
        painter.fillRect(QRect(r.left(), r.top(), bar_w, r.height()), accent_c)

        # Testo cartella
        x = r.left() + bar_w + 8
        text_color = QColor("white") if selected else QColor("#D8D8D8")
        f = QFont("Segoe UI", 9, QFont.Weight.Bold)
        painter.setFont(f)
        painter.setPen(text_color)

        # Conteggio figli
        total_c  = _count_connections(node)
        active_c = sum(1 for c in _iter_connections(node)
                       if c.id in self._connected_ids)

        # Testo nome
        avail_w = r.width() - (x - r.left()) - 60
        fm = QFontMetrics(f)
        name_elided = fm.elidedText(node.name, Qt.TextElideMode.ElideRight, avail_w)
        painter.drawText(QRect(x, r.top(), avail_w, r.height()),
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         name_elided)

        # Badge conteggio  "2/5"
        if total_c > 0:
            badge_txt = f"{active_c}/{total_c}" if active_c else str(total_c)
            badge_color = accent_c if active_c else QColor("#444444")
            self._draw_badge(painter, r.right() - 36, r.center().y(),
                             badge_txt, badge_color)

        # Separatore inferiore
        painter.setPen(QPen(QColor("#1E1E1E"), 1))
        painter.drawLine(r.left() + bar_w, r.bottom(), r.right(), r.bottom())

    # ── CONNESSIONE ───────────────────────────────────────────

    def _draw_connection(self, painter, r, node, selected, hovered):
        proto  = node.protocol.value if hasattr(node.protocol, "value") else str(node.protocol)
        p_color = QColor(PROTO_COLOR.get(proto, "#888888"))

        # Sfondo
        if selected:
            bg = QColor(ACCENT_COLOR)
        elif hovered:
            bg = QColor("#181818")
        else:
            bg = QColor("#111111")
        painter.fillRect(r, bg)

        # Guida verticale sinistra (1px, colore protocollo sbiadito)
        guide_x = r.left() + 2
        painter.setPen(QPen(QColor(p_color.red(), p_color.green(), p_color.blue(), 60), 1))
        painter.drawLine(guide_x, r.top() + 4, guide_x, r.bottom() - 4)

        x = r.left() + 10

        # ── Indicatore stato (cerchio colorato a sinistra) ──
        status_color = self._get_status_color(node)
        self._draw_status_dot(painter, x + 4, r.center().y(), status_color)
        x += 16

        # ── Badge protocollo ──
        proto_short = PROTO_SHORT.get(proto, proto[:3])
        badge_w = self._draw_proto_badge(painter, x, r.top() + 7, proto_short, p_color, selected)
        x += badge_w + 6

        # ── Nome ──
        f_name = QFont("Segoe UI", 9, QFont.Weight.DemiBold)
        name_c = QColor("white") if selected else QColor(TEXT_COLOR)
        painter.setFont(f_name)
        painter.setPen(name_c)
        avail = r.right() - x - 4
        fm = QFontMetrics(f_name)
        name_elided = fm.elidedText(node.name, Qt.TextElideMode.ElideRight, avail)
        painter.drawText(QRect(x, r.top() + 4, avail, 18),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         name_elided)

        # ── Host:porta (riga 2) ──
        if node.hostname:
            f_host = QFont("Segoe UI", 8)
            host_c = QColor("#CCCCCC") if selected else QColor("#666666")
            painter.setFont(f_host)
            painter.setPen(host_c)
            host_txt = f"{node.hostname}:{node.port}"
            painter.drawText(QRect(x, r.top() + 24, avail, 16),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                             host_txt)

        # Separatore leggero
        if not selected:
            painter.setPen(QPen(QColor("#181818"), 1))
            painter.drawLine(r.left() + 12, r.bottom(), r.right(), r.bottom())

    # ── Helpers ───────────────────────────────────────────────

    def _get_status_color(self, node) -> QColor:
        if node.id in self._connected_ids:
            return QColor("#4EC94E")        # verde brillante — connesso
        ping = self._ping_status.get(node.hostname)
        if ping is True:
            return QColor("#26A69A")        # teal — raggiungibile (ping OK)
        if ping is False:
            return QColor("#EF5350")        # rosso — non raggiungibile
        return QColor("#3A3A3A")            # grigio — stato sconosciuto

    def _draw_status_dot(self, painter, cx, cy, color: QColor):
        r_dot = 5
        painter.setPen(Qt.PenStyle.NoPen)
        # Alone esterno semi-trasparente
        glow = QColor(color.red(), color.green(), color.blue(), 50)
        painter.setBrush(glow)
        painter.drawEllipse(cx - r_dot - 2, cy - r_dot - 2,
                            (r_dot + 2) * 2, (r_dot + 2) * 2)
        # Cerchio pieno
        painter.setBrush(color)
        painter.drawEllipse(cx - r_dot, cy - r_dot, r_dot * 2, r_dot * 2)

    def _draw_proto_badge(self, painter, x, y, text: str,
                          color: QColor, selected: bool) -> int:
        f = QFont("Segoe UI", 7, QFont.Weight.Bold)
        painter.setFont(f)
        fm = QFontMetrics(f)
        tw = fm.horizontalAdvance(text)
        pad_h, pad_v = 5, 2
        bw = tw + pad_h * 2
        bh = fm.height() + pad_v * 2

        bg = QColor(color.red(), color.green(), color.blue(),
                    255 if selected else 45)
        border = QColor(color.red(), color.green(), color.blue(),
                        200 if selected else 120)

        painter.setPen(QPen(border, 1))
        painter.setBrush(bg)
        painter.drawRoundedRect(QRectF(x, y, bw, bh), 3, 3)

        painter.setPen(QColor("white") if selected else color)
        painter.drawText(QRect(x, y, bw, bh),
                         Qt.AlignmentFlag.AlignCenter, text)
        return bw

    def _draw_badge(self, painter, cx, cy, text: str, color: QColor):
        f = QFont("Segoe UI", 8, QFont.Weight.Bold)
        painter.setFont(f)
        fm = QFontMetrics(f)
        tw = fm.horizontalAdvance(text)
        pad = 5
        bw  = max(tw + pad * 2, 22)
        bh  = 16
        bx  = cx - bw // 2
        by  = cy - bh // 2

        bg = QColor(color.red(), color.green(), color.blue(), 30)
        painter.setPen(QPen(color, 1))
        painter.setBrush(bg)
        painter.drawRoundedRect(QRectF(bx, by, bw, bh), 8, 8)
        painter.setPen(color)
        painter.drawText(QRect(bx, by, bw, bh), Qt.AlignmentFlag.AlignCenter, text)


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────
def _iter_connections(node):
    from core.models import ContainerInfo
    if isinstance(node, ContainerInfo):
        for c in node.children:
            yield from _iter_connections(c)
    else:
        yield node


def _count_connections(node) -> int:
    return sum(1 for _ in _iter_connections(node))


# ─────────────────────────────────────────────────────────────
# Panel
# ─────────────────────────────────────────────────────────────
class ConnectionTreePanel(QWidget):
    connection_activated     = pyqtSignal(object)
    connection_selected      = pyqtSignal(object)
    new_connection_requested = pyqtSignal(object)
    new_folder_requested     = pyqtSignal(object)
    delete_requested         = pyqtSignal(object)
    rename_requested         = pyqtSignal(object)
    edit_requested           = pyqtSignal(object)
    add_to_bookmarks         = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(210)
        self._root: Optional['RootNode'] = None
        self._delegate = _ConnDelegate()
        self._setup_ui()

    # ── UI ────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QWidget()
        header.setFixedHeight(34)
        header.setStyleSheet(
            f"background:{CARD_COLOR}; border-bottom:1px solid #2A2A2A;"
        )
        hl = QHBoxLayout(header)
        hl.setContentsMargins(6, 2, 4, 2)
        hl.setSpacing(2)

        for icon, tip, cb in [
            ("＋",  "Nuova connessione", self._on_add_connection),
            ("📁",  "Nuova cartella",    self._on_add_folder),
            ("✕",  "Elimina",           self._on_delete),
            ("⊞",  "Espandi tutto",     self._on_expand_all),
            ("⊟",  "Comprimi tutto",    self._on_collapse_all),
        ]:
            hl.addWidget(self._tool_btn(icon, tip, cb))
        hl.addStretch()
        layout.addWidget(header)

        # Albero
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(16)
        self.tree.setMouseTracking(True)
        self.tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.setItemDelegate(self._delegate)
        self.tree.setStyleSheet(f"""
            QTreeWidget {{
                background:#111111; color:{TEXT_COLOR};
                border:none; outline:none;
            }}
            QTreeWidget::item {{ border:none; padding:0; }}
            QTreeWidget::item:selected {{ background:{ACCENT_COLOR}; }}
            QTreeWidget::branch {{
                background:#111111;
            }}
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {{
                image: none; border-image: none;
            }}
            QScrollBar:vertical {{
                background:#0D0D0D; width:6px; border:none;
            }}
            QScrollBar::handle:vertical {{
                background:#2A2A2A; border-radius:3px; min-height:20px;
            }}
            QScrollBar::handle:vertical:hover {{ background:{ACCENT_COLOR}; }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height:0; }}
        """)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        self.tree.itemClicked.connect(self._on_single_click)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.tree)

        # Legenda
        legend = self._build_legend()
        layout.addWidget(legend)

        # Ricerca
        search_bar = QWidget()
        search_bar.setFixedHeight(32)
        search_bar.setStyleSheet(
            f"background:{CARD_COLOR}; border-top:1px solid #2A2A2A;"
        )
        sl = QHBoxLayout(search_bar)
        sl.setContentsMargins(8, 2, 8, 2)
        lbl = QLabel("🔍")
        lbl.setStyleSheet(f"color:{SUB_COLOR}; background:transparent;")
        sl.addWidget(lbl)
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Cerca connessione...")
        self.search_box.setStyleSheet(f"""
            QLineEdit {{ background:transparent; color:{TEXT_COLOR};
                        border:none; font-size:11px; }}
        """)
        self.search_box.textChanged.connect(self._on_search)
        sl.addWidget(self.search_box)
        layout.addWidget(search_bar)

    def _build_legend(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet(f"background:#0D0D0D; border-top:1px solid #1A1A1A;")
        w.setFixedHeight(20)
        lay = QHBoxLayout(w)
        lay.setContentsMargins(8, 2, 8, 2)
        lay.setSpacing(10)
        for dot_color, label in [
            ("#4EC94E", "connesso"),
            ("#26A69A", "raggiungibile"),
            ("#EF5350", "offline"),
            ("#3A3A3A", "sconosciuto"),
        ]:
            dot_lbl = QLabel(f"<span style='color:{dot_color}; font-size:8pt'>●</span>"
                             f" <span style='color:#555; font-size:8pt'>{label}</span>")
            dot_lbl.setStyleSheet("background:transparent;")
            lay.addWidget(dot_lbl)
        lay.addStretch()
        return w

    def _tool_btn(self, icon: str, tip: str, cb) -> QPushButton:
        btn = QPushButton(icon)
        btn.setFixedSize(26, 26)
        btn.setToolTip(tip)
        btn.setStyleSheet(f"""
            QPushButton {{ background:transparent; color:{TEXT_COLOR};
                          border:none; border-radius:3px; font-size:13px; }}
            QPushButton:hover   {{ background:#2D2D2D; }}
            QPushButton:pressed {{ background:{ACCENT_COLOR}; }}
        """)
        btn.clicked.connect(cb)
        return btn

    # ── Dati ──────────────────────────────────────────────────

    def load_tree(self, root: 'RootNode'):
        self._root = root
        self.tree.clear()
        root_item = QTreeWidgetItem(self.tree)
        root_item.setData(0, Qt.ItemDataRole.UserRole, root)
        root_item.setSizeHint(0, QSize(0, _ConnDelegate.ROOT_H))
        self._populate_item(root_item, root, depth=0)
        root_item.setExpanded(True)

    def _populate_item(self, parent_item: QTreeWidgetItem, container, depth: int = 0):
        from core.models import ContainerInfo
        for child in container.children:
            item = QTreeWidgetItem(parent_item)
            item.setData(0, Qt.ItemDataRole.UserRole, child)
            item.setData(0, Qt.ItemDataRole.UserRole + 1, depth)
            if isinstance(child, ContainerInfo):
                item.setSizeHint(0, QSize(0, _ConnDelegate.FOLD_H))
                item.setExpanded(child.is_expanded)
                self._populate_item(item, child, depth + 1)
            else:
                item.setSizeHint(0, QSize(0, _ConnDelegate.CONN_H))

    def set_connected_ids(self, ids: Set[str]):
        """Aggiorna quali connessioni hanno una tab aperta."""
        self._delegate._connected_ids = ids
        self.tree.viewport().update()

    def set_ping_status(self, status: Dict[str, Optional[bool]]):
        """Aggiorna stato ping per ogni hostname."""
        self._delegate._ping_status = status
        self.tree.viewport().update()

    def refresh(self):
        if self._root:
            connected = set(self._delegate._connected_ids)
            ping      = dict(self._delegate._ping_status)
            self.load_tree(self._root)
            self._delegate._connected_ids = connected
            self._delegate._ping_status   = ping
            self.tree.viewport().update()

    # ── Interazione ───────────────────────────────────────────

    def _get_selected_node(self):
        items = self.tree.selectedItems()
        return items[0].data(0, Qt.ItemDataRole.UserRole) if items else None

    def _on_single_click(self, item, col):
        node = item.data(0, Qt.ItemDataRole.UserRole)
        if node:
            self.connection_selected.emit(node)

    def _on_double_click(self, item, col):
        node = item.data(0, Qt.ItemDataRole.UserRole)
        from core.models import ContainerInfo, RootNode
        if node and not isinstance(node, (ContainerInfo, RootNode)):
            self.connection_activated.emit(node)
        else:
            item.setExpanded(not item.isExpanded())

    def _show_context_menu(self, pos: QPoint):
        node = self._get_selected_node()
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background:#1A1A1A; color:{TEXT_COLOR}; border:1px solid #333;
                    font-size:12px; }}
            QMenu::item {{ padding:5px 20px 5px 12px; }}
            QMenu::item:selected {{ background:{ACCENT_COLOR}; color:white; }}
            QMenu::separator {{ background:#2A2A2A; height:1px; margin:3px 8px; }}
        """)
        from core.models import ContainerInfo, RootNode

        if node and not isinstance(node, (ContainerInfo, RootNode)):
            is_connected = node.id in self._delegate._connected_ids
            connect_label = "⏹  Disconnetti" if is_connected else "▶  Connetti"
            menu.addAction(connect_label, lambda: self.connection_activated.emit(node))
            menu.addSeparator()
            menu.addAction("★  Aggiungi ai Bookmark", lambda: self.add_to_bookmarks.emit(node))
            menu.addSeparator()
            menu.addAction("✏  Proprietà",    lambda: self.edit_requested.emit(node))
            menu.addAction("📝  Rinomina",     lambda: self.rename_requested.emit(node))
            menu.addAction("⧉  Duplica",      lambda: self._duplicate(node))
            menu.addSeparator()
            menu.addAction("✕  Elimina",      lambda: self.delete_requested.emit(node))
        else:
            menu.addAction("＋  Nuova Connessione", lambda: self.new_connection_requested.emit(node))
            menu.addAction("📁  Nuova Cartella",     lambda: self.new_folder_requested.emit(node))
            if node and not isinstance(node, RootNode):
                menu.addSeparator()
                menu.addAction("✏  Proprietà",  lambda: self.edit_requested.emit(node))
                menu.addAction("✕  Elimina",    lambda: self.delete_requested.emit(node))

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _duplicate(self, node):
        cloned = node.clone()
        if node.parent:
            node.parent.add_child(cloned)
        self.refresh()

    def _on_add_connection(self):
        self.new_connection_requested.emit(self._get_selected_node())

    def _on_add_folder(self):
        self.new_folder_requested.emit(self._get_selected_node())

    def _on_delete(self):
        node = self._get_selected_node()
        if node:
            self.delete_requested.emit(node)

    def _on_expand_all(self):
        self.tree.expandAll()

    def _on_collapse_all(self):
        self.tree.collapseAll()
        if self.tree.topLevelItemCount() > 0:
            self.tree.topLevelItem(0).setExpanded(True)

    def _on_search(self, text: str):
        def _visit(item: QTreeWidgetItem) -> bool:
            node = item.data(0, Qt.ItemDataRole.UserRole)
            from core.models import ConnectionInfo
            if isinstance(node, ConnectionInfo) and not node.is_container:
                label = (node.name + " " + (node.hostname or "")).lower()
            else:
                label = (node.name if node else item.text(0)).lower()
            match = text.lower() in label if text else True
            child_match = any(_visit(item.child(i)) for i in range(item.childCount()))
            visible = match or child_match
            item.setHidden(not visible)
            if child_match and text:
                item.setExpanded(True)
            return visible

        for i in range(self.tree.topLevelItemCount()):
            _visit(self.tree.topLevelItem(i))

    def select_connection(self, conn):
        def _find(parent_item):
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                if child.data(0, Qt.ItemDataRole.UserRole) is conn:
                    return child
                found = _find(child)
                if found:
                    return found
            return None
        for i in range(self.tree.topLevelItemCount()):
            item = _find(self.tree.topLevelItem(i))
            if item:
                self.tree.setCurrentItem(item)
                self.tree.scrollToItem(item)
                break
