"""
Report Dialog: genera ed esporta report CSV e HTML.
"""
from __future__ import annotations
import os
from typing import List, TYPE_CHECKING

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QCheckBox, QSpinBox, QFileDialog, QTextEdit, QMessageBox,
    QGroupBox, QRadioButton
)
from themes.dark_theme import ACCENT_COLOR, TEXT_COLOR, SUB_COLOR, BG_COLOR

if TYPE_CHECKING:
    from core.models import ConnectionInfo


class ReportDialog(QDialog):
    def __init__(self, connections: List["ConnectionInfo"] = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Esporta Report")
        self.setMinimumSize(560, 480)
        self._connections = connections or []
        self._setup_ui()
        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet(f"""
            QDialog   {{ background:{BG_COLOR}; color:{TEXT_COLOR}; }}
            QLabel    {{ background:transparent; color:{TEXT_COLOR}; }}
            QTextEdit {{ background:#0C0C0C; color:{TEXT_COLOR}; border:1px solid #2A2A2A;
                        border-radius:3px; font-family:Consolas,monospace; font-size:11px; }}
            QGroupBox {{ border:1px solid #2A2A2A; border-radius:4px;
                         margin-top:8px; color:{SUB_COLOR}; padding:8px; }}
            QGroupBox::title {{ subcontrol-origin:margin; padding:0 4px; color:{SUB_COLOR}; }}
            QSpinBox  {{ background:#1E1E1E; color:{TEXT_COLOR}; border:1px solid #333;
                        border-radius:3px; padding:3px 6px; }}
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("Esporta Report Aziendale")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{ACCENT_COLOR};")
        layout.addWidget(title)

        # Formato
        fmt_group = QGroupBox("Formato")
        fmt_layout = QHBoxLayout(fmt_group)
        self._html_rb = QRadioButton("HTML (apribile nel browser)")
        self._html_rb.setChecked(True)
        self._csv_inv_rb = QRadioButton("CSV Inventario")
        self._csv_log_rb = QRadioButton("CSV Log sessioni")
        for rb in [self._html_rb, self._csv_inv_rb, self._csv_log_rb]:
            rb.setStyleSheet(f"color:{TEXT_COLOR};")
            fmt_layout.addWidget(rb)
        layout.addWidget(fmt_group)

        # Opzioni log
        log_group = QGroupBox("Opzioni log sessioni")
        log_layout = QHBoxLayout(log_group)
        days_lbl = QLabel("Includi ultimi:")
        days_lbl.setStyleSheet(f"color:{SUB_COLOR};")
        log_layout.addWidget(days_lbl)
        self._days_spin = QSpinBox()
        self._days_spin.setRange(1, 365)
        self._days_spin.setValue(30)
        self._days_spin.setFixedWidth(70)
        log_layout.addWidget(self._days_spin)
        log_layout.addWidget(QLabel("giorni di log"))
        log_layout.addStretch()
        layout.addWidget(log_group)

        # Preview area
        prev_lbl = QLabel("Anteprima:")
        prev_lbl.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px;")
        layout.addWidget(prev_lbl)
        self._preview = QTextEdit()
        self._preview.setReadOnly(True)
        self._preview.setFixedHeight(160)
        layout.addWidget(self._preview)

        # Bottoni
        btn_row = QHBoxLayout()
        preview_btn = QPushButton("Aggiorna anteprima")
        preview_btn.setStyleSheet(
            f"QPushButton {{ background:#2A2A2A; color:{TEXT_COLOR}; border:1px solid #444;"
            f" border-radius:3px; padding:5px 14px; }}"
            f"QPushButton:hover {{ background:#3A3A3A; }}"
        )
        preview_btn.clicked.connect(self._update_preview)
        btn_row.addWidget(preview_btn)
        btn_row.addStretch()

        export_btn = QPushButton("Esporta...")
        export_btn.setStyleSheet(f"""
            QPushButton {{ background:{ACCENT_COLOR}; color:white; border:none;
                          border-radius:3px; padding:5px 18px; font-weight:bold; }}
            QPushButton:hover {{ background:#0088DD; }}
        """)
        export_btn.clicked.connect(self._export)
        btn_row.addWidget(export_btn)

        close_btn = QPushButton("Chiudi")
        close_btn.setStyleSheet(
            f"QPushButton {{ background:#2A2A2A; color:{TEXT_COLOR}; border:1px solid #444;"
            f" border-radius:4px; padding:5px 14px; }}"
            f"QPushButton:hover {{ background:#3A3A3A; }}"
        )
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

        self._update_preview()

    def _get_events(self):
        try:
            from core.session_logger import SessionLogger
            return SessionLogger.get_instance().get_all(days=self._days_spin.value())
        except Exception:
            return []

    def _update_preview(self):
        from core.reporter import connections_to_csv, sessions_to_csv, generate_html_report
        events = self._get_events()
        if self._html_rb.isChecked():
            html = generate_html_report(self._connections, events)
            lines = html.split("\n")
            self._preview.setPlainText("\n".join(lines[:40]) + "\n... (HTML)")
        elif self._csv_inv_rb.isChecked():
            csv_txt = connections_to_csv(self._connections)
            self._preview.setPlainText(csv_txt[:2000])
        else:
            csv_txt = sessions_to_csv(events)
            self._preview.setPlainText(csv_txt[:2000])

    def _export(self):
        from core.reporter import (
            connections_to_csv, sessions_to_csv,
            generate_html_report, save_file
        )
        events = self._get_events()

        if self._html_rb.isChecked():
            path, _ = QFileDialog.getSaveFileName(
                self, "Salva report HTML", "report_pymremoteng.html",
                "HTML Files (*.html)"
            )
            if path:
                save_file(generate_html_report(self._connections, events), path)
        elif self._csv_inv_rb.isChecked():
            path, _ = QFileDialog.getSaveFileName(
                self, "Salva inventario CSV", "inventario_connessioni.csv",
                "CSV Files (*.csv)"
            )
            if path:
                save_file(connections_to_csv(self._connections), path)
        else:
            path, _ = QFileDialog.getSaveFileName(
                self, "Salva log sessioni CSV", "log_sessioni.csv",
                "CSV Files (*.csv)"
            )
            if path:
                save_file(sessions_to_csv(events), path)

        if path:
            reply = QMessageBox.information(
                self, "Esportazione completata",
                f"File salvato:\n{path}\n\nAprirlo ora?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.Yes:
                if os.path.isfile(path):
                    os.startfile(path)
                else:
                    QMessageBox.warning(self, "Errore", "Il file non è più disponibile.")
