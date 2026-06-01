"""
Pannello Bookmarks con cartelle e sottocartelle.
I bookmark sono shortcut a connessioni, organizzabili in cartelle personalizzate.
"""
from __future__ import annotations
import json
import os
import uuid
from typing import Dict, List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem,
    QMenu, QLabel, QPushButton, QInputDialog, QMessageBox, QDialog,
    QFormLayout, QLineEdit, QComboBox, QSpinBox, QDialogButtonBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QPoint, QSize
from PyQt6.QtGui import QFont, QColor, QAction

from themes.dark_theme import ACCENT_COLOR, CARD_COLOR, TEXT_COLOR, SUB_COLOR

BOOKMARKS_PATH = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "PyMRemoteNG", "bookmarks.json"
)

PROTO_ICON = {
    "SSH2": "🟢", "SSH1": "🟢", "RDP": "🔵",
    "VNC": "🟠", "ARD": "🟠",
    "HTTP": "🌐", "HTTPS": "🔒",
    "Telnet": "🟡",
}


# ── Dialogo aggiungi/modifica bookmark ─────────────────────────────────────
class BookmarkDialog(QDialog):
    def __init__(self, bm: Optional[dict] = None, folders: List[str] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bookmark" if bm is None else "Modifica Bookmark")
        self.setFixedSize(380, 320)
        self.setStyleSheet(f"background:#1A1A1A; color:{TEXT_COLOR};")

        layout = QVBoxLayout(self)
        form   = QFormLayout()

        def field(ph=""):
            le = QLineEdit()
            le.setPlaceholderText(ph)
            le.setStyleSheet(f"background:#0C0C0C; color:{TEXT_COLOR}; border:1px solid #333; border-radius:3px; padding:4px 6px;")
            return le

        self.name_edit = field("Es. Web Server Prod")
        self.host_edit = field("192.168.1.1")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(22)
        self.port_spin.setStyleSheet(f"background:#0C0C0C; color:{TEXT_COLOR}; border:1px solid #333; border-radius:3px; padding:2px;")
        self.user_edit = field("root")

        self.proto_combo = QComboBox()
        for p in ["SSH2", "SSH1", "RDP", "VNC", "Telnet", "HTTP", "HTTPS"]:
            self.proto_combo.addItem(p)
        self.proto_combo.setStyleSheet(f"""
            QComboBox {{ background:#0C0C0C; color:{TEXT_COLOR}; border:1px solid #333; border-radius:3px; padding:2px 6px; }}
            QComboBox QAbstractItemView {{ background:#1A1A1A; color:{TEXT_COLOR}; selection-background-color:{ACCENT_COLOR}; }}
        """)
        self.proto_combo.currentTextChanged.connect(self._update_port)

        self.folder_combo = QComboBox()
        self.folder_combo.addItem("— Nessuna cartella —")
        for f in (folders or []):
            self.folder_combo.addItem(f)
        self.folder_combo.setStyleSheet(self.proto_combo.styleSheet())

        lbl_style = f"color:{SUB_COLOR}; background:transparent;"
        for lbl_txt, w in [
            ("Nome:", self.name_edit),
            ("Host:", self.host_edit),
            ("Porta:", self.port_spin),
            ("Protocollo:", self.proto_combo),
            ("Utente:", self.user_edit),
            ("Cartella:", self.folder_combo),
        ]:
            lbl = QLabel(lbl_txt)
            lbl.setStyleSheet(lbl_style)
            form.addRow(lbl, w)

        layout.addLayout(form)
        layout.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.button(QDialogButtonBox.StandardButton.Ok).setStyleSheet(
            f"background:{ACCENT_COLOR}; color:white; border:none; border-radius:3px; padding:4px 16px;"
        )
        btns.button(QDialogButtonBox.StandardButton.Cancel).setStyleSheet(
            f"background:#2A2A2A; color:{TEXT_COLOR}; border:none; border-radius:3px; padding:4px 16px;"
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        if bm:
            self.name_edit.setText(bm.get("name", ""))
            self.host_edit.setText(bm.get("hostname", ""))
            self.port_spin.setValue(bm.get("port", 22))
            self.user_edit.setText(bm.get("username", ""))
            idx = self.proto_combo.findText(bm.get("protocol", "SSH2"))
            if idx >= 0:
                self.proto_combo.setCurrentIndex(idx)
            folder = bm.get("folder", "")
            fidx = self.folder_combo.findText(folder) if folder else 0
            self.folder_combo.setCurrentIndex(max(0, fidx))

    def _update_port(self, proto: str):
        defaults = {"SSH2": 22, "SSH1": 22, "RDP": 3389, "VNC": 5900,
                    "Telnet": 23, "HTTP": 80, "HTTPS": 443}
        self.port_spin.setValue(defaults.get(proto, 22))

    def get_data(self) -> dict:
        folder = self.folder_combo.currentText()
        if folder.startswith("—"):
            folder = ""
        return {
            "name":     self.name_edit.text().strip() or self.host_edit.text().strip(),
            "hostname": self.host_edit.text().strip(),
            "port":     self.port_spin.value(),
            "protocol": self.proto_combo.currentText(),
            "username": self.user_edit.text().strip(),
            "folder":   folder,
        }


# ── Pannello principale ─────────────────────────────────────────────────────
class BookmarksPanel(QWidget):
    """
    Pannello dei Bookmark con cartelle/sottocartelle.
    Double-click su un bookmark emette connection_activated con un ConnectionInfo-like dict.
    """
    connection_activated = pyqtSignal(object)   # emette ConnectionInfo

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background:#111111;")
        self._bookmarks: List[dict] = []   # [{id, name, hostname, port, protocol, username, folder}, ...]
        self._folders:   List[str]  = []   # nomi cartelle
        self._load()
        self._setup_ui()

    # ── Persistenza ─────────────────────────────────────────────────────────

    def _load(self):
        if not os.path.exists(BOOKMARKS_PATH):
            return
        try:
            with open(BOOKMARKS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._bookmarks = data.get("bookmarks", [])
            self._folders   = data.get("folders", [])
        except Exception:
            pass

    def _save(self):
        os.makedirs(os.path.dirname(BOOKMARKS_PATH), exist_ok=True)
        with open(BOOKMARKS_PATH, "w", encoding="utf-8") as f:
            json.dump({"bookmarks": self._bookmarks, "folders": self._folders}, f, indent=2)

    # ── UI ──────────────────────────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QLabel("  ★  Bookmarks")
        header.setFixedHeight(32)
        header.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        header.setStyleSheet(f"background:#1A1A1A; color:{SUB_COLOR}; border-bottom:1px solid #2A2A2A; padding-left:4px;")
        layout.addWidget(header)

        # Toolbar
        tb = QWidget()
        tb.setFixedHeight(30)
        tb.setStyleSheet(f"background:{CARD_COLOR}; border-bottom:1px solid #222;")
        tb_l = QHBoxLayout(tb)
        tb_l.setContentsMargins(4, 1, 4, 1)
        tb_l.setSpacing(2)

        for icon, tip, cb in [
            ("＋",  "Nuovo Bookmark",  self._on_add_bookmark),
            ("📁",  "Nuova Cartella",  self._on_add_folder),
            ("✏",  "Modifica",        self._on_edit),
            ("✕",  "Elimina",         self._on_delete),
        ]:
            btn = QPushButton(icon)
            btn.setFixedSize(26, 24)
            btn.setToolTip(tip)
            btn.setStyleSheet(f"""
                QPushButton {{ background:transparent; color:{TEXT_COLOR}; border:none;
                               border-radius:3px; font-size:12px; }}
                QPushButton:hover  {{ background:#2D2D2D; }}
                QPushButton:pressed {{ background:{ACCENT_COLOR}; }}
            """)
            btn.clicked.connect(cb)
            tb_l.addWidget(btn)
        tb_l.addStretch()
        layout.addWidget(tb)

        # Albero
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setIndentation(14)
        self.tree.setRootIsDecorated(True)
        self.tree.setAnimated(True)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.setStyleSheet(f"""
            QTreeWidget {{
                background:#111111; color:{TEXT_COLOR};
                border:none; font-size:11px; outline:none;
            }}
            QTreeWidget::item {{ padding:3px 2px; border:none; }}
            QTreeWidget::item:selected {{ background:{ACCENT_COLOR}; color:white; }}
            QTreeWidget::item:hover:!selected {{ background:#1E1E1E; }}
            QTreeWidget::branch {{ background:#111111; }}
        """)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self.tree)

        self._refresh_tree()

    def _refresh_tree(self):
        self.tree.clear()

        # Raccogli i bookmark per cartella
        grouped: Dict[str, List[dict]] = {}
        no_folder = []
        for bm in self._bookmarks:
            folder = bm.get("folder", "")
            if folder:
                grouped.setdefault(folder, []).append(bm)
            else:
                no_folder.append(bm)

        # Cartelle
        for folder in self._folders:
            folder_item = QTreeWidgetItem(self.tree, [f"  📁  {folder}"])
            folder_item.setData(0, Qt.ItemDataRole.UserRole, {"_type": "folder", "name": folder})
            folder_item.setFont(0, QFont("Segoe UI", 9, QFont.Weight.DemiBold))
            folder_item.setForeground(0, QColor("#C8C8C8"))
            folder_item.setExpanded(True)
            for bm in grouped.get(folder, []):
                self._add_bm_item(folder_item, bm)

        # Bookmark senza cartella
        for bm in no_folder:
            self._add_bm_item(self.tree.invisibleRootItem(), bm)

        if self.tree.topLevelItemCount() == 0:
            info = QTreeWidgetItem(self.tree, ["  Nessun bookmark"])
            info.setForeground(0, QColor(SUB_COLOR))
            info.setFlags(Qt.ItemFlag.NoItemFlags)

    def _add_bm_item(self, parent, bm: dict):
        proto = bm.get("protocol", "SSH2")
        icon  = PROTO_ICON.get(proto, "⚪")
        label = f"  {icon}  {bm.get('name', bm.get('hostname', '?'))}"
        item  = QTreeWidgetItem(parent, [label])
        item.setData(0, Qt.ItemDataRole.UserRole, bm)
        item.setToolTip(0, f"{bm.get('hostname', '')}:{bm.get('port', '')} [{proto}]")
        return item

    # ── Azioni ──────────────────────────────────────────────────────────────

    def _on_double_click(self, item: QTreeWidgetItem, _):
        bm = item.data(0, Qt.ItemDataRole.UserRole)
        if not bm or bm.get("_type") == "folder":
            item.setExpanded(not item.isExpanded())
            return
        self._open_bookmark(bm)

    def _open_bookmark(self, bm: dict):
        from core.models import ConnectionInfo, ProtocolType
        c = ConnectionInfo()
        c.name     = bm.get("name", bm.get("hostname", ""))
        c.hostname = bm.get("hostname", "")
        c.port     = bm.get("port", 22)
        c.username = bm.get("username", "")
        try:
            c.protocol = ProtocolType(bm.get("protocol", "SSH2"))
        except ValueError:
            c.protocol = ProtocolType.SSH2
        self.connection_activated.emit(c)

    def _on_add_bookmark(self):
        dlg = BookmarkDialog(folders=self._folders, parent=self)
        if dlg.exec():
            bm = dlg.get_data()
            if not bm["hostname"]:
                return
            bm["id"] = str(uuid.uuid4())
            self._bookmarks.append(bm)
            self._save()
            self._refresh_tree()

    def _on_add_folder(self):
        name, ok = QInputDialog.getText(self, "Nuova Cartella", "Nome cartella:")
        if ok and name.strip() and name.strip() not in self._folders:
            self._folders.append(name.strip())
            self._save()
            self._refresh_tree()

    def _on_edit(self):
        item = self._get_selected()
        if not item:
            return
        bm = item.data(0, Qt.ItemDataRole.UserRole)
        if not bm or bm.get("_type") == "folder":
            return
        dlg = BookmarkDialog(bm=bm, folders=self._folders, parent=self)
        if dlg.exec():
            bm.update(dlg.get_data())
            self._save()
            self._refresh_tree()

    def _on_delete(self):
        item = self._get_selected()
        if not item:
            return
        bm = item.data(0, Qt.ItemDataRole.UserRole)
        if not bm:
            return
        if bm.get("_type") == "folder":
            name = bm["name"]
            r = QMessageBox.question(self, "Elimina Cartella",
                f"Eliminare la cartella '{name}' e tutti i suoi bookmark?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if r == QMessageBox.StandardButton.Yes:
                self._folders = [f for f in self._folders if f != name]
                self._bookmarks = [b for b in self._bookmarks if b.get("folder") != name]
                self._save()
                self._refresh_tree()
        else:
            bid = bm.get("id")
            self._bookmarks = [b for b in self._bookmarks if b.get("id") != bid]
            self._save()
            self._refresh_tree()

    def _on_context_menu(self, pos: QPoint):
        item = self.tree.itemAt(pos)
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{ background:#1A1A1A; color:{TEXT_COLOR}; border:1px solid #333; }}
            QMenu::item:selected {{ background:{ACCENT_COLOR}; }}
        """)
        if item:
            bm = item.data(0, Qt.ItemDataRole.UserRole)
            if bm and bm.get("_type") != "folder":
                menu.addAction("▶  Connetti", lambda: self._open_bookmark(bm))
                menu.addSeparator()
                menu.addAction("✏  Modifica",  self._on_edit)
                menu.addAction("✕  Elimina",   self._on_delete)
            elif bm and bm.get("_type") == "folder":
                menu.addAction("✕  Elimina cartella", self._on_delete)
        menu.addSeparator()
        menu.addAction("＋  Nuovo Bookmark", self._on_add_bookmark)
        menu.addAction("📁  Nuova Cartella",  self._on_add_folder)
        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _get_selected(self) -> Optional[QTreeWidgetItem]:
        items = self.tree.selectedItems()
        return items[0] if items else None

    def add_from_connection(self, conn):
        """Aggiunge un bookmark da una ConnectionInfo esistente."""
        bm = {
            "id":       str(uuid.uuid4()),
            "name":     conn.name,
            "hostname": conn.hostname,
            "port":     conn.port,
            "protocol": conn.protocol.value if hasattr(conn.protocol, "value") else str(conn.protocol),
            "username": conn.username,
            "folder":   "",
        }
        # Chiedi in quale cartella metterlo
        if self._folders:
            items = ["— Nessuna cartella —"] + self._folders
            choice, ok = QInputDialog.getItem(self, "Aggiungi Bookmark",
                "Seleziona cartella:", items, 0, False)
            if not ok:
                return
            bm["folder"] = "" if choice.startswith("—") else choice

        self._bookmarks.append(bm)
        self._save()
        self._refresh_tree()
