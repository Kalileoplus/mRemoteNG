"""
User Manager Dialog: gestione utenti e ruoli aziendali.
Solo gli admin possono aprirlo.
"""
from __future__ import annotations
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QCheckBox, QMessageBox, QFormLayout, QGroupBox,
    QDialogButtonBox
)
from themes.dark_theme import ACCENT_COLOR, TEXT_COLOR, SUB_COLOR, BG_COLOR
from core.user_manager import UserManager, ROLES, AppUser


# ─────────────────────────────────────────────────────────────
# Dialogo add/edit singolo utente
# ─────────────────────────────────────────────────────────────
class UserEditDialog(QDialog):
    def __init__(self, user: AppUser = None, parent=None):
        super().__init__(parent)
        self._user = user
        self.setWindowTitle("Nuovo utente" if user is None else "Modifica utente")
        self.setMinimumWidth(400)
        self._setup_ui()
        self._apply_style()
        if user:
            self._populate(user)

    def _apply_style(self):
        self.setStyleSheet(f"""
            QDialog   {{ background:{BG_COLOR}; color:{TEXT_COLOR}; }}
            QLabel    {{ background:transparent; color:{TEXT_COLOR}; }}
            QLineEdit, QComboBox {{
                background:#1E1E1E; color:{TEXT_COLOR};
                border:1px solid #333; border-radius:3px; padding:4px 8px; min-height:24px;
            }}
            QLineEdit:focus {{ border-color:{ACCENT_COLOR}; }}
            QGroupBox {{ border:1px solid #2A2A2A; border-radius:4px;
                         margin-top:8px; color:{SUB_COLOR}; }}
            QGroupBox::title {{ subcontrol-origin:margin; padding:0 4px; }}
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        form = QFormLayout()
        form.setSpacing(8)

        self._username_edit = QLineEdit()
        self._username_edit.setPlaceholderText("mario.rossi")
        form.addRow("Username:", self._username_edit)

        self._display_edit = QLineEdit()
        self._display_edit.setPlaceholderText("Mario Rossi")
        form.addRow("Nome visualizzato:", self._display_edit)

        self._role_combo = QComboBox()
        for key, info in ROLES.items():
            self._role_combo.addItem(info["label"], key)
        form.addRow("Ruolo:", self._role_combo)

        self._pw_edit = QLineEdit()
        self._pw_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw_edit.setPlaceholderText(
            "Nuova password" if self._user else "Password obbligatoria"
        )
        form.addRow("Password:", self._pw_edit)

        self._pw_confirm = QLineEdit()
        self._pw_confirm.setEchoMode(QLineEdit.EchoMode.Password)
        self._pw_confirm.setPlaceholderText("Conferma password")
        form.addRow("Conferma:", self._pw_confirm)

        self._active_cb = QCheckBox("Utente attivo")
        self._active_cb.setChecked(True)
        self._active_cb.setStyleSheet(f"color:{TEXT_COLOR};")
        form.addRow("", self._active_cb)

        layout.addLayout(form)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.setStyleSheet(f"""
            QPushButton {{ background:{ACCENT_COLOR}; color:white; border:none;
                          border-radius:3px; padding:5px 18px; }}
            QPushButton:hover {{ background:#0088DD; }}
            QPushButton[text="Cancel"] {{ background:#2A2A2A; color:{TEXT_COLOR};
                                          border:1px solid #444; }}
        """)
        btns.accepted.connect(self._validate)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _populate(self, user: AppUser):
        self._username_edit.setText(user.username)
        self._display_edit.setText(user.display_name)
        idx = self._role_combo.findData(user.role)
        if idx >= 0:
            self._role_combo.setCurrentIndex(idx)
        self._active_cb.setChecked(user.active)

    def _validate(self):
        username = self._username_edit.text().strip()
        pw       = self._pw_edit.text()
        pw_conf  = self._pw_confirm.text()

        if not username:
            QMessageBox.warning(self, "Errore", "Username obbligatorio.")
            return
        if not self._user and not pw:
            QMessageBox.warning(self, "Errore", "Password obbligatoria per i nuovi utenti.")
            return
        if pw and pw != pw_conf:
            QMessageBox.warning(self, "Errore", "Le password non coincidono.")
            return
        self.accept()

    def get_data(self) -> dict:
        return {
            "username":     self._username_edit.text().strip(),
            "display_name": self._display_edit.text().strip(),
            "role":         self._role_combo.currentData(),
            "password":     self._pw_edit.text(),
            "active":       self._active_cb.isChecked(),
        }


# ─────────────────────────────────────────────────────────────
# Dialogo principale gestione utenti
# ─────────────────────────────────────────────────────────────
class UserManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        # VULN-10: verifica permessi prima di costruire la UI
        current = UserManager.get_instance().current_user()
        if not current or not current.can("manage_users"):
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(0, self.reject)
            self._unauthorized = True
            return
        self._unauthorized = False
        self.setWindowTitle("Gestione Utenti")
        self.setMinimumSize(700, 480)
        self._mgr = UserManager.get_instance()
        self._setup_ui()
        self._apply_style()
        self._refresh_table()

    def _apply_style(self):
        self.setStyleSheet(f"""
            QDialog {{ background:{BG_COLOR}; color:{TEXT_COLOR}; }}
            QLabel  {{ background:transparent; color:{TEXT_COLOR}; }}
        """)

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 16)

        title = QLabel("Gestione Utenti e Ruoli")
        title.setFont(QFont("Segoe UI", 13, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{ACCENT_COLOR};")
        layout.addWidget(title)

        subtitle = QLabel(
            "Utente admin predefinito: admin / admin  (cambia la password al primo accesso)"
        )
        subtitle.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px;")
        layout.addWidget(subtitle)

        # Toolbar
        toolbar = QHBoxLayout()
        add_btn = QPushButton("+ Nuovo utente")
        add_btn.setStyleSheet(f"""
            QPushButton {{ background:{ACCENT_COLOR}; color:white; border:none;
                          border-radius:3px; padding:5px 14px; font-weight:bold; }}
            QPushButton:hover {{ background:#0088DD; }}
        """)
        add_btn.clicked.connect(self._add_user)
        toolbar.addWidget(add_btn)

        self._edit_btn = QPushButton("Modifica")
        self._edit_btn.setEnabled(False)
        self._edit_btn.clicked.connect(self._edit_user)
        toolbar.addWidget(self._edit_btn)

        self._del_btn = QPushButton("Elimina")
        self._del_btn.setEnabled(False)
        self._del_btn.clicked.connect(self._delete_user)
        toolbar.addWidget(self._del_btn)

        for btn in [self._edit_btn, self._del_btn]:
            btn.setStyleSheet(
                f"QPushButton {{ background:#2A2A2A; color:{TEXT_COLOR}; border:1px solid #444;"
                f" border-radius:3px; padding:5px 14px; }}"
                f"QPushButton:hover {{ background:#3A3A3A; }}"
                f"QPushButton:disabled {{ color:#555; border-color:#333; }}"
            )

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Tabella
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Username", "Nome", "Ruolo", "Stato", "Ultimo accesso"]
        )
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.setColumnWidth(0, 130)
        self._table.setColumnWidth(2, 130)
        self._table.setColumnWidth(3, 80)
        self._table.setColumnWidth(4, 160)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.verticalHeader().setVisible(False)
        self._table.setShowGrid(False)
        self._table.setAlternatingRowColors(True)
        self._table.itemSelectionChanged.connect(self._on_selection)
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

    def _refresh_table(self):
        self._table.setRowCount(0)
        for user in self._mgr.all():
            row = self._table.rowCount()
            self._table.insertRow(row)
            self._table.setItem(row, 0, QTableWidgetItem(user.username))
            self._table.setItem(row, 1, QTableWidgetItem(user.display_name))

            role_item = QTableWidgetItem(user.role_label())
            role_item.setForeground(QColor(user.role_color()))
            self._table.setItem(row, 2, role_item)

            status_item = QTableWidgetItem("Attivo" if user.active else "Disabilitato")
            status_item.setForeground(
                QColor("#4EC94E") if user.active else QColor("#EF5350")
            )
            self._table.setItem(row, 3, status_item)
            self._table.setItem(row, 4, QTableWidgetItem(user.last_login or "Mai"))

            # Store user id in column 0
            self._table.item(row, 0).setData(Qt.ItemDataRole.UserRole, user.id)

    def _on_selection(self):
        has_sel = bool(self._table.selectedItems())
        self._edit_btn.setEnabled(has_sel)
        self._del_btn.setEnabled(has_sel)

    def _selected_user_id(self):
        rows = self._table.selectedItems()
        if not rows:
            return None
        row = self._table.currentRow()
        item = self._table.item(row, 0)
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _add_user(self):
        dlg = UserEditDialog(parent=self)
        if dlg.exec():
            d = dlg.get_data()
            if self._mgr.get_by_username(d["username"]):
                QMessageBox.warning(self, "Errore", f"Username '{d['username']}' già esistente.")
                return
            self._mgr.add(d["username"], d["display_name"], d["role"], d["password"])
            self._refresh_table()

    def _edit_user(self):
        uid = self._selected_user_id()
        if not uid:
            return
        user = self._mgr.get(uid)
        if not user:
            return
        dlg = UserEditDialog(user=user, parent=self)
        if dlg.exec():
            d = dlg.get_data()
            existing = self._mgr.get_by_username(d["username"])
            if existing and existing.id != uid:
                QMessageBox.warning(self, "Errore", f"Username '{d['username']}' già in uso.")
                return
            self._mgr.update(uid, d["display_name"], d["role"], d["password"], d["active"])
            self._refresh_table()

    def _delete_user(self):
        uid = self._selected_user_id()
        if not uid:
            return
        user = self._mgr.get(uid)
        if not user:
            return
        # Impedisci eliminazione dell'unico admin
        admins = [u for u in self._mgr.all() if u.role == "admin"]
        if user.role == "admin" and len(admins) <= 1:
            QMessageBox.warning(self, "Errore", "Non puoi eliminare l'unico amministratore.")
            return
        r = QMessageBox.question(
            self, "Elimina utente",
            f"Eliminare l'utente '{user.username}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if r == QMessageBox.StandardButton.Yes:
            self._mgr.delete(uid)
            self._refresh_table()
