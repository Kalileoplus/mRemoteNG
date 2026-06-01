"""
Pannello Macros: salva e invia snippet di testo/comandi alle sessioni.
"""
import json, os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QListWidget, QListWidgetItem, QTextEdit,
    QInputDialog, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from themes.dark_theme import ACCENT_COLOR, CARD_COLOR, TEXT_COLOR, SUB_COLOR

MACROS_PATH = os.path.join(
    os.environ.get("APPDATA", os.path.expanduser("~")),
    "PyMRemoteNG", "macros.json"
)


class MacrosPanel(QWidget):
    run_macro = pyqtSignal(str)   # testo da inviare alla sessione corrente

    def __init__(self):
        super().__init__()
        self._macros: list[dict] = []
        self.setStyleSheet(f"background:#111111;")
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        header = QLabel("  ●  Macros")
        header.setFixedHeight(32)
        header.setFont(QFont("Segoe UI", 10, QFont.Weight.Bold))
        header.setStyleSheet(f"background:#1A1A1A; color:{SUB_COLOR}; border-bottom:1px solid #2A2A2A; padding-left:6px;")
        layout.addWidget(header)

        # Toolbar
        tb = QWidget(); tb.setFixedHeight(30)
        tb.setStyleSheet(f"background:#161616; border-bottom:1px solid #2A2A2A;")
        tb_layout = QHBoxLayout(tb)
        tb_layout.setContentsMargins(4,2,4,2); tb_layout.setSpacing(2)

        for icon, tip, cb in [
            ("＋", "Nuova macro",    self._new_macro),
            ("✕", "Elimina macro",  self._delete_macro),
            ("▶", "Esegui macro",   self._run_macro),
        ]:
            btn = QPushButton(icon)
            btn.setFixedSize(26, 24)
            btn.setToolTip(tip)
            btn.setStyleSheet(f"""
                QPushButton {{ background:transparent; color:{TEXT_COLOR}; border:none; border-radius:3px; font-size:12px; }}
                QPushButton:hover {{ background:#2A2A2A; }}
                QPushButton:pressed {{ background:{ACCENT_COLOR}; }}
            """)
            btn.clicked.connect(cb)
            tb_layout.addWidget(btn)
        tb_layout.addStretch()
        layout.addWidget(tb)

        # Lista macro
        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet(f"""
            QListWidget {{ background:#0E0E0E; color:{TEXT_COLOR}; border:none; font-size:12px; }}
            QListWidget::item {{ padding:6px 8px; border-bottom:1px solid #1E1E1E; }}
            QListWidget::item:hover {{ background:#1E1E1E; }}
            QListWidget::item:selected {{ background:{ACCENT_COLOR}; color:white; }}
        """)
        self.list_widget.itemDoubleClicked.connect(self._run_macro)
        layout.addWidget(self.list_widget)

        # Anteprima testo
        self.preview = QTextEdit()
        self.preview.setMaximumHeight(80)
        self.preview.setPlaceholderText("Seleziona una macro per vedere il contenuto...")
        self.preview.setFont(QFont("Consolas", 10))
        self.preview.setStyleSheet(f"background:#0C0C0C; color:#888; border:none; border-top:1px solid #2A2A2A; padding:4px;")
        self.preview.setReadOnly(True)
        layout.addWidget(self.preview)
        self.list_widget.itemSelectionChanged.connect(self._on_select)

    def _load(self):
        try:
            with open(MACROS_PATH, encoding="utf-8") as f:
                self._macros = json.load(f)
        except Exception:
            self._macros = [
                {"name": "Aggiorna sistema",   "text": "sudo apt update && sudo apt upgrade -y\r"},
                {"name": "Stato servizi",      "text": "systemctl list-units --type=service --state=running\r"},
                {"name": "Spazio disco",       "text": "df -h\r"},
                {"name": "Processi CPU",       "text": "top\r"},
                {"name": "Informazioni rete",  "text": "ip addr show\r"},
            ]
        self._refresh_list()

    def _save(self):
        os.makedirs(os.path.dirname(MACROS_PATH), exist_ok=True)
        with open(MACROS_PATH, "w", encoding="utf-8") as f:
            json.dump(self._macros, f, indent=2, ensure_ascii=False)

    def _refresh_list(self):
        self.list_widget.clear()
        for m in self._macros:
            self.list_widget.addItem(f"● {m['name']}")

    def _on_select(self):
        idx = self.list_widget.currentRow()
        if 0 <= idx < len(self._macros):
            self.preview.setPlainText(self._macros[idx]["text"])

    def _new_macro(self):
        name, ok = QInputDialog.getText(self, "Nuova Macro", "Nome macro:")
        if not ok or not name.strip(): return
        text, ok2 = QInputDialog.getMultiLineText(self, "Contenuto Macro",
                                                  "Testo/Comando da inviare:")
        if not ok2: return
        self._macros.append({"name": name.strip(), "text": text})
        self._refresh_list()
        self._save()

    def _delete_macro(self):
        idx = self.list_widget.currentRow()
        if idx < 0: return
        r = QMessageBox.question(self, "Elimina",
            f"Eliminare la macro '{self._macros[idx]['name']}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if r == QMessageBox.StandardButton.Yes:
            self._macros.pop(idx)
            self._refresh_list()
            self._save()

    def _run_macro(self, *_):
        idx = self.list_widget.currentRow()
        if 0 <= idx < len(self._macros):
            self.run_macro.emit(self._macros[idx]["text"])
