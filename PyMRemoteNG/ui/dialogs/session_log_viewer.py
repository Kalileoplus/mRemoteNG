"""
Session Log Viewer: visualizza, filtra, esporta e svuota i log di sessione.
"""
from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QSpinBox, QMessageBox, QFileDialog, QFrame
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

        # Info dimensione
        self._size_lbl = QLabel("")
        self._size_lbl.setStyleSheet(
            f"color:{SUB_COLOR}; font-size:10px; background:transparent;"
        )
        layout.addWidget(self._size_lbl)

        # Separatore
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#2A2A2A;")
        layout.addWidget(sep)

        # Footer
        footer = QHBoxLayout()
        footer.setSpacing(8)

        _btn_style = (
            "QPushButton {{ background:{bg}; color:{fg}; border:1px solid {bd};"
            " border-radius:4px; padding:6px 14px; font-size:11px; }}"
            "QPushButton:hover {{ background:{hv}; }}"
            "QPushButton:disabled {{ color:#555; border-color:#333; background:#1A1A1A; }}"
        )

        export_btn = QPushButton("📥  Esporta CSV")
        export_btn.setToolTip("Salva tutti gli eventi filtrati in un file CSV")
        export_btn.setStyleSheet(_btn_style.format(
            bg=ACCENT_COLOR, fg="white", bd=ACCENT_COLOR, hv="#0088DD"
        ))
        export_btn.clicked.connect(self._export_csv)
        footer.addWidget(export_btn)

        purge_btn = QPushButton("🗑  Svuota log vecchi…")
        purge_btn.setToolTip(
            "Elimina i file di log più vecchi del numero di giorni selezionato.\n"
            "I log recenti vengono conservati."
        )
        purge_btn.setStyleSheet(_btn_style.format(
            bg="#2A1A1A", fg="#EF5350", bd="#4A2A2A", hv="#3A1A1A"
        ))
        purge_btn.clicked.connect(self._purge_logs)
        footer.addWidget(purge_btn)

        footer.addStretch()

        close_btn = QPushButton("Chiudi")
        close_btn.setStyleSheet(_btn_style.format(
            bg="#2A2A2A", fg=TEXT_COLOR, bd="#444", hv="#3A3A3A"
        ))
        close_btn.clicked.connect(self.accept)
        footer.addWidget(close_btn)
        layout.addLayout(footer)

    def _load(self):
        try:
            from core.session_logger import SessionLogger, _get_log_dir
            days = self._days_spin.value()
            self._all_events = SessionLogger.get_instance().get_all(days=days)
            self._update_size_label(_get_log_dir())
        except Exception:
            self._all_events = []
        self._apply_filters()

    def _update_size_label(self, log_dir: str):
        """Mostra numero di file e dimensione totale della cartella log."""
        try:
            import os
            files  = [f for f in os.listdir(log_dir)
                      if f.startswith("session_") and f.endswith(".json")]
            total  = sum(os.path.getsize(os.path.join(log_dir, f)) for f in files)
            size_s = (f"{total/1024:.0f} KB" if total < 1_048_576
                      else f"{total/1_048_576:.1f} MB")
            self._size_lbl.setText(
                f"📁  {len(files)} file log  ·  {size_s} su disco  ·  {log_dir}"
            )
        except Exception:
            self._size_lbl.setText("")

    def _export_csv(self):
        """Esporta gli eventi attualmente visibili in CSV."""
        if not self._all_events:
            QMessageBox.information(self, "Esporta", "Nessun evento da esportare.")
            return
        from datetime import datetime as dt
        default = f"log_export_{dt.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self, "Salva CSV", default, "CSV (*.csv);;Tutti i file (*)"
        )
        if not path:
            return
        try:
            from core.reporter import sessions_to_csv, save_file
            # Usa gli eventi filtrati (quelli in tabella), non tutti
            visible = self._get_visible_events()
            csv_data = sessions_to_csv(visible)
            save_file(csv_data, path)
            QMessageBox.information(
                self, "Esporta CSV",
                f"Esportati {len(visible)} eventi in:\n{path}"
            )
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Esportazione fallita:\n{e}")

    def _get_visible_events(self):
        """Ritorna gli eventi attualmente visibili nella tabella (filtrati)."""
        search = self._search.text().lower()
        type_f = self._type_combo.currentText()
        return [
            e for e in self._all_events
            if (type_f == "Tutti" or e.type == type_f)
            and (not search or search in e.host.lower()
                 or search in e.user.lower()
                 or search in e.detail.lower())
        ]

    def _purge_logs(self):
        """Elimina i file di log più vecchi di N giorni con conferma."""
        days = self._days_spin.value()
        r = QMessageBox.question(
            self, "Svuota log vecchi",
            f"Elimina tutti i file di log più vecchi di {days} giorni?\n\n"
            f"I log degli ultimi {days} giorni vengono conservati.\n"
            f"Questa operazione non è reversibile.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if r != QMessageBox.StandardButton.Yes:
            return
        try:
            from core.session_logger import SessionLogger
            removed = SessionLogger.get_instance().purge_before(days_to_keep=days)
            QMessageBox.information(
                self, "Svuota log",
                f"Eliminati {removed} file di log."
                + ("\nNessun file era più vecchio del limite." if removed == 0 else "")
            )
            self._load()
        except Exception as e:
            QMessageBox.critical(self, "Errore", f"Pulizia fallita:\n{e}")

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
