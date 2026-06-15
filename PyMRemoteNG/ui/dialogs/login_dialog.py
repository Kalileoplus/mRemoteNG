"""
Schermata di login all'avvio dell'applicazione.
Forza il cambio password se l'account usa ancora la password di default.
"""
from __future__ import annotations
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFrame, QWidget, QSizePolicy
)
from themes.dark_theme import ACCENT_COLOR, TEXT_COLOR, SUB_COLOR, BG_COLOR


_FIELD_STYLE = (
    f"QLineEdit {{ background:#1E1E1E; color:{TEXT_COLOR}; border:1px solid #333;"
    f" border-radius:4px; padding:8px 12px; font-size:13px; }}"
    f"QLineEdit:focus {{ border-color:{ACCENT_COLOR}; }}"
)
_BTN_PRIMARY = (
    f"QPushButton {{ background:{ACCENT_COLOR}; color:white; border:none;"
    f" border-radius:4px; padding:9px 0; font-size:13px; font-weight:bold; }}"
    f"QPushButton:hover {{ background:#0088DD; }}"
    f"QPushButton:disabled {{ background:#1A2A3A; color:#444; }}"
)


class ChangePasswordDialog(QDialog):
    """Dialog per il cambio password obbligatorio al primo accesso."""

    def __init__(self, user, parent=None):
        super().__init__(parent)
        self._user = user
        self.setWindowTitle("Cambio password obbligatorio")
        self.setFixedWidth(400)
        self.setWindowFlags(
            Qt.WindowType.Dialog | Qt.WindowType.WindowTitleHint
        )
        self.setStyleSheet(f"QDialog {{ background:{BG_COLOR}; color:{TEXT_COLOR}; }}")
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 28, 28, 24)
        lay.setSpacing(14)

        warn = QLabel("⚠️  Cambio password richiesto")
        warn.setStyleSheet(
            "color:#FFC107; font-size:14px; font-weight:bold; background:transparent;"
        )
        lay.addWidget(warn)

        info = QLabel(
            f"L'account <b>{self._user.username}</b> usa ancora la password di default.<br>"
            "Scegli una nuova password per continuare."
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px; background:transparent;")
        lay.addWidget(info)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet("color:#2A2A2A;")
        lay.addWidget(sep)

        self._new_pw  = QLineEdit()
        self._new_pw.setPlaceholderText("Nuova password (min. 8 caratteri)")
        self._new_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._new_pw.setStyleSheet(_FIELD_STYLE)
        lay.addWidget(self._new_pw)

        self._conf_pw = QLineEdit()
        self._conf_pw.setPlaceholderText("Conferma nuova password")
        self._conf_pw.setEchoMode(QLineEdit.EchoMode.Password)
        self._conf_pw.setStyleSheet(_FIELD_STYLE)
        self._conf_pw.returnPressed.connect(self._on_confirm)
        lay.addWidget(self._conf_pw)

        self._err_lbl = QLabel("")
        self._err_lbl.setStyleSheet(
            "color:#EF5350; font-size:11px; background:transparent;"
        )
        self._err_lbl.setWordWrap(True)
        lay.addWidget(self._err_lbl)

        self._ok_btn = QPushButton("Salva nuova password")
        self._ok_btn.setStyleSheet(_BTN_PRIMARY)
        self._ok_btn.clicked.connect(self._on_confirm)
        lay.addWidget(self._ok_btn)

    def _on_confirm(self):
        new_pw   = self._new_pw.text()
        conf_pw  = self._conf_pw.text()

        if len(new_pw) < 8:
            self._err_lbl.setText("La password deve contenere almeno 8 caratteri.")
            return
        if new_pw != conf_pw:
            self._err_lbl.setText("Le password non coincidono.")
            return
        from core.user_manager import UserManager
        ok = UserManager.get_instance().change_password(self._user.id, new_pw)
        if ok:
            self.accept()
        else:
            self._err_lbl.setText(
                "Password non accettata: troppo corta, troppo comune o uguale a quella attuale."
            )


class LoginDialog(QDialog):
    """Schermata di login all'avvio. Blocca l'accesso all'app senza credenziali valide."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Nexus — Accesso")
        self.setFixedWidth(400)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.MSWindowsFixedSizeDialogHint
        )
        self.setStyleSheet(f"QDialog {{ background:{BG_COLOR}; color:{TEXT_COLOR}; }}")
        from ui.icon_generator import create_app_icon
        self.setWindowIcon(create_app_icon())
        self._attempts = 0
        self._locked   = False
        self._build_ui()

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(36, 36, 36, 28)
        lay.setSpacing(0)

        # Logo / titolo
        logo = QLabel("🖥")
        logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        logo.setStyleSheet("font-size:48px; background:transparent;")
        lay.addWidget(logo)

        title = QLabel("Nexus")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        title.setStyleSheet(f"color:{ACCENT_COLOR}; background:transparent;")
        lay.addWidget(title)

        sub = QLabel("Inserisci le tue credenziali per accedere")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet(f"color:{SUB_COLOR}; font-size:11px; background:transparent;")
        lay.addWidget(sub)

        lay.addSpacing(24)

        self._user_edit = QLineEdit()
        self._user_edit.setPlaceholderText("Username")
        self._user_edit.setStyleSheet(_FIELD_STYLE)
        self._user_edit.returnPressed.connect(self._focus_password)
        lay.addWidget(self._user_edit)

        lay.addSpacing(8)

        self._pass_edit = QLineEdit()
        self._pass_edit.setPlaceholderText("Password")
        self._pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._pass_edit.setStyleSheet(_FIELD_STYLE)
        self._pass_edit.returnPressed.connect(self._on_login)
        lay.addWidget(self._pass_edit)

        lay.addSpacing(10)

        self._err_lbl = QLabel("")
        self._err_lbl.setWordWrap(True)
        self._err_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._err_lbl.setStyleSheet(
            "color:#EF5350; font-size:11px; background:transparent;"
        )
        self._err_lbl.setFixedHeight(32)
        lay.addWidget(self._err_lbl)

        lay.addSpacing(4)

        self._login_btn = QPushButton("Accedi")
        self._login_btn.setStyleSheet(_BTN_PRIMARY)
        self._login_btn.clicked.connect(self._on_login)
        lay.addWidget(self._login_btn)

        lay.addSpacing(16)

        hint = QLabel(
            "Prima installazione: admin / admin\n"
            "(verrà richiesto il cambio password)"
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setStyleSheet(
            f"color:#333; font-size:10px; background:transparent;"
        )
        lay.addWidget(hint)

    def _focus_password(self):
        self._pass_edit.setFocus()

    def _on_login(self):
        if self._locked:
            return

        username = self._user_edit.text().strip()
        password = self._pass_edit.text()

        if not username or not password:
            self._err_lbl.setText("Inserisci username e password.")
            return

        from core.user_manager import UserManager
        um   = UserManager.get_instance()
        user = um.authenticate(username, password)

        if user:
            self._pass_edit.clear()
            # Forza cambio password se necessario
            if user.must_change_password:
                cpd = ChangePasswordDialog(user, self)
                if cpd.exec() != QDialog.DialogCode.Accepted:
                    self._err_lbl.setText(
                        "Devi impostare una nuova password per accedere."
                    )
                    return
            self.accept()
        else:
            self._pass_edit.clear()
            self._attempts += 1
            remaining = max(0, 5 - self._attempts)
            if self._attempts >= 5:
                self._locked = True
                self._login_btn.setEnabled(False)
                self._err_lbl.setText(
                    "Troppi tentativi falliti. Attendi 30 secondi."
                )
                QTimer.singleShot(30_000, self._unlock)
            else:
                self._err_lbl.setText(
                    f"Credenziali non valide. "
                    f"({remaining} tentativi rimanenti)"
                )

    def _unlock(self):
        self._locked   = False
        self._attempts = 0
        self._login_btn.setEnabled(True)
        self._err_lbl.setText("")
