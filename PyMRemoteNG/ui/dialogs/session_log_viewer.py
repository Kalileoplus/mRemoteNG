"""
Session Log Viewer: visualizza e filtra i log di sessione.
"""
from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QSpinBox
)
from themes.dark_theme import ACCENT_COLOR, TEXT_COLOR, SUB_COLOR, BG_COLOR

_EVENT_COLORS = {
    "CONNECT":    "#4EC94E",
    "DISCONNECT": "#FFC107",
    "COMMAND":    "#5BA8E5",
    "ERROR":      "#EF5350",
    "AUTH":       "#9B7FE8",
}


class SessionLogViewer(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Log Sessioni")
        self.setMinimumSize(900, 580)
        self._all_events = []
        self._setup_ui()
        self._apply_style()
        self._load()

    def _apply_style(self):
        self.setStyleSheet(f"""
            QDialog  {{ background:{BG_COLOR}; color:{TEXT_COLOR}; }}
            QLabel   {{ background:transparent; color:{TEXT_COLOR}; }}
            QLineEdit, QComboBox, QSpinBox {{
                background:#1E1E1E; color:{TEXT_COLOR};
                border:1px solid #333; border-radius:3px; padding:3px 8px;
            }}
            QLineEdit:focus {{ border-color:{ACCENT_COLOR}; }}
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("Log Sessioni")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{ACCENT_COLOR};")
        layout.addWidget(title)

        # Filtri
        filter_row = QHBoxLayout()

        search_lbl = QLabel("Cerca:")
        search_lbl.setFixedWidth(50)
        self._search = QLineEdit()
        self._search.setPlaceholderText("host, utente, dettaglio...")
        self._search.setFixedWidth(200)
        self._search.textChanged.connect(self._apply_filters)
        filter_row.addWidget(search_lbl)
        filter_row.addWidget(self._search)

        type_lbl = QLabel("Tipo:")
        type_lbl.setFixedWidth(40)
        self._type_combo = QComboBox()
        self._type_combo.addItems(["Tutti", "CONNECT", "DISCONNECT", "COMMAND", "ERROR", "AUTH"])
        self._type_combo.setFixedWidth(130)
        self._type_combo.currentIndexChanged.connect(self._apply_filters)
        filter_row.addWidget(type_lbl)
        filter_row.addWidget(self._type_combo)

        days_lbl = QLabel("Giorni:")
        days_lbl.setFixedWidth(50)
        self._days_spin = QSpinBox()
        self._days_spin.setRange(1, 365)
        self._days_spin.setValue(30)
        self._days_spin.setFixedWidth(60)
        filter_row.addWidget(days_lbl)
        filter_row.addWidget(self._days_spin)

        reload_btn = QPushButton("Ricarica")
        reload_btn.setStyleSheet(f"""
            QPushButton {{ background:{ACCENT_COLOR}; color:white; border:none;
                          border-radius:3px; padding:4px 12px; font-size:11px; }}
            QPushButton:hover {{ background:#0088DD; }}
        """)
        reload_btn.clicked.connect(self._load)
        filter_row.addWidget(reload_btn)
        filter_row.addStretch()

        self._count_lbl = QLabel("")
        self._count_lbl.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px;")
        filter_row.addWidget(self._count_lbl)
        layout.addLayout(filter_row)

        # Tabella
        self._table = QTableWidget(0, 6)
        self._table.setHorizontalHeaderLabels(
            ["Timestamp", "Tipo", "Utente", "Host", "Protocollo", "Dettaglio"]
        )
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(1, 100)
        self._table.setColumnWidth(2, 100)
        self._table.setColumnWidth(3, 140)
        self._table.setColumnWidth(4, 90)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(f"""
            QTableWidget {{ background:{BG_COLOR}; color:{TEXT_COLOR};
                           border:1px solid #2A2A2A; alternate-background-color:#111; }}
            QHeaderView::section {{ background:#1A1A1A; color:{SUB_COLOR};
                                    border:none; padding:4px 8px; font-size:11px; }}
            QTableWidget::item:selected {{ background:#1A3A5A; color:white; }}
        """)
        layout.addWidget(self._table)

        # Footer
        footer = QHBoxLayout()
        footer.addStretch()
        close_btn = QPushButton("Chiudi")
        close_btn.setStyleSheet(
            f"QPushButton {{ background:#2A2A2A; color:{TEXT_COLOR}; border:1px solid #444;"
            f" border-radius:4px; padding:6px 16px; }}"
            f"QPushButton:hover {{ background:#3A3A3A; }}"
        )
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        layout.addLayout(footer)

    def _load(self):
        try:
            from core.session_logger import SessionLogger
            days = self._days_spin.value()
            self._all_events = SessionLogger.get_instance().get_all(days=days)
        except Exception:
            self._all_events = []
        self._apply_filters()

    def _apply_filters(self):
        search  = self._search.text().lower()
        type_f  = self._type_combo.currentText()

        filtered = [
            e for e in self._all_events
            if (type_f == "Tutti" or e.type == type_f)
            and (not search or search in e.host.lower()
                 or search in e.user.lower()
                 or search in e.detail.lower())
        ]

        self._table.setRowCount(0)
        for ev in filtered:
            row = self._table.rowCount()
            self._table.insertRow(row)
            color = _EVENT_COLORS.get(ev.type, "#888888")
            values = [ev.ts, ev.type, ev.user, ev.host, ev.protocol, ev.detail]
            for col, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                if col == 1:
                    item.setForeground(QColor(color))
                self._table.setItem(row, col, item)

        self._count_lbl.setText(f"{len(filtered)} eventi")
