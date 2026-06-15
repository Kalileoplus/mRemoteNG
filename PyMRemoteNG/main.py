"""
Nexus - entry point
"""
import sys
import os
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="paramiko")
warnings.filterwarnings("ignore", category=UserWarning, module="paramiko")

# Operazioni Windows pre-QApplication
if sys.platform == "win32":
    try:
        import ctypes
        # Icona nella taskbar: ID univoco evita raggruppamento con python.exe
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Nexus.RemoteManager.1")
        # Nascondi la finestra CMD nera
        hwnd_console = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd_console:
            ctypes.windll.user32.ShowWindow(hwnd_console, 0)
        ctypes.windll.kernel32.FreeConsole()
    except Exception:
        pass

# Aggiungi la root del progetto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.main_window import MainWindow
from ui.dialogs.login_dialog import LoginDialog
from themes.dark_theme import DARK_QSS


def main():
    # Abilita High DPI
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Nexus")
    app.setOrganizationName("Nexus")

    # Icona globale dell'app (taskbar + titolo + alt+tab)
    from ui.icon_generator import create_app_icon
    _app_icon = create_app_icon()
    app.setWindowIcon(_app_icon)

    # Tema dark globale
    app.setStyleSheet(DARK_QSS)

    # Font di default più grande
    font = QFont("Segoe UI", 12)
    app.setFont(font)

    # Login obbligatorio prima di mostrare la finestra principale
    login = LoginDialog()
    if login.exec() != LoginDialog.DialogCode.Accepted:
        sys.exit(0)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
