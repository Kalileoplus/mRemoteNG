"""
Pannello albero connessioni - con delegate personalizzato per visualizzazione
a due righe (nome + host:porta), icone protocollo colorate, auto-expand.
"""
from __future__ import annotations
from typing import Optional, TYPE_CHECKING

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QMenu, QLineEdit, QHBoxLayout, QLabel, QPushButton,
    QAbstractItemView, QStyledItemDelegate, QApplication, QStyle
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QSize, QRect
from PyQt6.QtGui import (
    QIcon, QFont, QAction, QColor, QPainter, QFontMetrics, QPalette
)

from themes.dark_theme import ACCENT_COLOR, CARD_COLOR, TEXT_COLOR, SUB_COLOR

if TYPE_CHECKING:
    from core.models import ConnectionInfo, ContainerInfo, RootNode


PROTO_ICON = {
    "SSH2": "🟢", "SSH1": "🟢",
    "RDP":  "🔵",
    "VNC":  "🟠", "ARD": "🟠",
    "HTTP": "🌐", "HTTPS": "🔒",
    "Telnet": "🟡", "Rlogin": "🟡", "RAW": "🟡",
}

PROTO_COLOR = {
    "SSH2": "#4EC94E", "SSH1": "#4EC94E",
    "RDP":  "#4E9EEC",
    "VNC":  "#EC8C4E", "ARD": "#EC8C4E",
    "HTTP": "#A78FEC", "HTTPS": "#A78FEC",
    "Telnet": "#E0E06A", "Rlogin": "#E0E06A", "RAW": "#888888",
}


class _ConnDelegate(QStyledItemDelegate):
    """Delegate che disegna connessioni con nome + host su 2 righe."""

    ITEM_H = 42   # altezza voce connessione
    FOLD_H = 24   # altezza voce cartella

    def sizeHint(self, option, index):
        node = index.data(Qt.ItemDataRole.UserRole)
        from core.models import ConnectionInfo
        h = self.ITEM_H if isinstance(node, ConnectionInfo) else self.FOLD_H
        return QSize(option.rect.width(), h)

    def paint(self, painter: QPainter, option, index):
        node = index.data(Qt.ItemDataRole.UserRole)
        from core.models import ConnectionInfo
        if not isinstance(node, ConnectionInfo):
            super().paint(painter, option, index)
            return

        painter.save()
        r = option.rect

        # Sfondo
        if option.state & QStyle.StateFlag.State_Selected:
            painter.fillRect(r, QColor(ACCENT_COLOR))
        elif option.state & QStyle.StateFlag.State_MouseOver:
            painter.fillRect(r, QColor("#1E2A1E"))
        else:
            painter.fillRect(r, QColor("#111111"))

        proto = node.protocol.value if hasattr(node.protocol, "value") else str(node.protocol)
        icon_ch = PROTO_ICON.get(proto, "⚪")
        c_name  = QColor("white") if (option.state & QStyle.StateFlag.State_Selected) else QColor(TEXT_COLOR)
        c_host  = QColor("#BBBBBB") if (option.state & QStyle.StateFlag.State_Selected) else QColor(SUB_COLOR)
        c_proto = QColor("white") if (option.state & QStyle.StateFlag.State_Selected) else QColor(PROTO_COLOR.get(proto, "#888888"))

        # Indentazione già inclusa in r.left()
        x = r.left() + 4

        # Icona protocollo (emoji)
        icon_font = QFont("Segoe UI Emoji")
        icon_font.setPointSize(11)
        painter.setFont(icon_font)
        painter.setPen(c_proto)
        icon_rect = QRect(x, r.top() + 4, 20, self.ITEM_H - 8)
        painter.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, icon_ch)

        tx = x + 24

        # Nome connessione (riga 1)
        f_name = QFont("Segoe UI", 9, QFont.Weight.DemiBold)
        painter.setFont(f_name)
        painter.setPen(c_name)
        name_rect = QRect(tx, r.top() + 4, r.right() - tx - 4, 18)
        fm = QFontMetrics(f_name)
        name_text = fm.elidedText(node.name, Qt.TextElideMode.ElideRight, name_rect.width())
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, name_text)

        # Host:porta (riga 2)
        f_host = QFont("Segoe UI", 8)
        painter.setFont(f_host)
        painter.setPen(c_host)
        host_rect = QRect(tx, r.top() + 22, r.right() - tx - 4, 16)
        host_text = f"{node.hostname}:{node.port}" if node.hostname else ""
        painter.drawText(host_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, host_text)

        painter.restore()


class ConnectionTreePanel(QWidget):
    """
    Pannello laterale con albero delle connessioni.
    Ogni voce mostra: icona protocollo colorata, nome (bold) e host:porta.
    Le cartelle si espandono automaticamente al caricamento.
    """
    connection_activated     = pyqtSignal(object)
    connection_selected      = pyqtSignal(object)
    new_connection_requested = pyqtSignal(object)
    new_folder_requested     = pyqtSignal(object)
    delete_requested         = pyqtSignal(object)
    rename_requested         = pyqtSignal(object)
    edit_requested           = pyqtSignal(object)
    add_to_bookmarks         = pyqtSignal(object)   # nuovo: aggiunge ai bookmark

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(200)
        self._root: Optional['RootNode'] = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setFixedHeight(34)
        toolbar.setStyleSheet(f"background-color: {CARD_COLOR}; border-bottom: 1px solid #2A2A2A;")
        tb_layout = QHBoxLayout(toolbar)
        tb_layout.setContentsMargins(4, 2, 4, 2)
        tb_layout.setSpacing(2)

        for icon, tip, cb in [
            ("＋", "Nuova Connessione", self._on_add_connection),
            ("📁", "Nuova Cartella",    self._on_add_folder),
            ("✕", "Elimina",           self._on_delete),
            ("⊞", "Espandi tutto",     self._on_expand_all),
            ("⊟", "Comprimi tutto",    self._on_collapse_all),
        ]:
            tb_layout.addWidget(self._make_tool_btn(icon, tip, cb))
        tb_layout.addStretch()
        layout.addWidget(toolbar)

        # Albero
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setRootIsDecorated(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(14)
        self.tree.setMouseTracking(True)
        self.tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.setItemDelegate(_ConnDelegate(self.tree))
        self.tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: #111111;
                color: {TEXT_COLOR};
                border: none;
                font-size: 10px;
                outline: none;
            }}
            QTreeWidget::item {{
                border: none;
                padding: 0px;
            }}
            QTreeWidget::item:selected {{
                background-color: {ACCENT_COLOR};
            }}
            QTreeWidget::branch {{
                background-color: #111111;
            }}
            QTreeWidget::branch:has-children:!has-siblings:closed,
            QTreeWidget::branch:closed:has-children:has-siblings {{
                image: none;
                border-image: none;
            }}
        """)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        self.tree.itemClicked.connect(self._on_single_click)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        layout.addWidget(self.tree)

        # Barra ricerca
        search_bar = QWidget()
        search_bar.setFixedHeight(32)
        search_bar.setStyleSheet(f"background-color: {CARD_COLOR}; border-top: 1px solid #2A2A2A;")
        sb = QHBoxLayout(search_bar)
        sb.setContentsMargins(6, 2, 6, 2)

        lbl = QLabel("🔍")
        lbl.setStyleSheet(f"color: {SUB_COLOR}; background: transparent;")
        sb.addWidget(lbl)

        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Cerca...")
        self.search_box.setStyleSheet(f"""
            QLineEdit {{
                background: transparent; color: {TEXT_COLOR};
                border: none; font-size: 11px;
            }}
        """)
        self.search_box.textChanged.connect(self._on_search)
        sb.addWidget(self.search_box)
        layout.addWidget(search_bar)

    def _make_tool_btn(self, icon: str, tooltip: str, callback) -> QPushButton:
        btn = QPushButton(icon)
        btn.setFixedSize(26, 26)
        btn.setToolTip(tooltip)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {TEXT_COLOR};
                border: none; border-radius: 3px; font-size: 13px;
            }}
            QPushButton:hover  {{ background-color: #2D2D2D; }}
            QPushButton:pressed {{ background-color: {ACCENT_COLOR}; }}
        """)
        btn.clicked.connect(callback)
        return btn

    def load_tree(self, root: 'RootNode'):
        self._root = root
        self.tree.clear()
        root_item = QTreeWidgetItem(self.tree, [root.name])
        root_item.setData(0, Qt.ItemDataRole.UserRole, root)
        root_item.setFont(0, QFont("Segoe UI", 10, QFont.Weight.Bold))
        root_item.setForeground(0, QColor(ACCENT_COLOR))
        self._populate_item(root_item, root)
        root_item.setExpanded(True)

    def _populate_item(self, parent_item: QTreeWidgetItem, container):
        from core.models import ContainerInfo
        for child in container.children:
            if isinstance(child, ContainerInfo):
                item = QTreeWidgetItem(parent_item, [f"  📁  {child.name}"])
                item.setData(0, Qt.ItemDataRole.UserRole, child)
                item.setFont(0, QFont("Segoe UI", 9, QFont.Weight.DemiBold))
                item.setForeground(0, QColor("#C8C8C8"))
                item.setExpanded(True)  # auto-espandi sempre
                self._populate_item(item, child)
            else:
                item = QTreeWidgetItem(parent_item, [""])
                item.setData(0, Qt.ItemDataRole.UserRole, child)
                item.setSizeHint(0, QSize(0, _ConnDelegate.ITEM_H))

    def _get_selected_node(self):
        items = self.tree.selectedItems()
        return items[0].data(0, Qt.ItemDataRole.UserRole) if items else None

    def _on_single_click(self, item: QTreeWidgetItem, col: int):
        node = item.data(0, Qt.ItemDataRole.UserRole)
        if node:
            self.connection_selected.emit(node)

    def _on_double_click(self, item: QTreeWidgetItem, col: int):
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
            QMenu {{ background-color: #1A1A1A; color: {TEXT_COLOR}; border: 1px solid #333; }}
            QMenu::item:selected {{ background-color: {ACCENT_COLOR}; }}
        """)
        from core.models import ContainerInfo, RootNode

        if node and not isinstance(node, (ContainerInfo, RootNode)):
            menu.addAction("▶  Connetti",      lambda: self.connection_activated.emit(node))
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

    def _duplicate(self, node: 'ConnectionInfo'):
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
        def search_item(item: QTreeWidgetItem) -> bool:
            node = item.data(0, Qt.ItemDataRole.UserRole)
            from core.models import ConnectionInfo
            label = (node.name + " " + node.hostname) if isinstance(node, ConnectionInfo) else item.text(0)
            match = text.lower() in label.lower()
            child_match = any(search_item(item.child(i)) for i in range(item.childCount()))
            visible = match or child_match or not text
            item.setHidden(not visible)
            if child_match:
                item.setExpanded(True)
            return visible

        for i in range(self.tree.topLevelItemCount()):
            search_item(self.tree.topLevelItem(i))

    def refresh(self):
        if self._root:
            self.load_tree(self._root)

    def select_connection(self, conn: 'ConnectionInfo'):
        def find_item(parent_item: QTreeWidgetItem) -> Optional[QTreeWidgetItem]:
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                if child.data(0, Qt.ItemDataRole.UserRole) is conn:
                    return child
                result = find_item(child)
                if result:
                    return result
            return None

        for i in range(self.tree.topLevelItemCount()):
            item = find_item(self.tree.topLevelItem(i))
            if item:
                self.tree.setCurrentItem(item)
                self.tree.scrollToItem(item)
                break
