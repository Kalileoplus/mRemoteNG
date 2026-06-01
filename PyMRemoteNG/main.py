"""
PyMRemoteNG - entry point
"""
import sys
import os
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="paramiko")
warnings.filterwarnings("ignore", category=UserWarning, module="paramiko")

# Nascondi e stacca la finestra CMD su Windows (nessuna finestra nera)
if sys.platform == "win32":
    try:
        import ctypes
        # Ottieni l'HWND della console e nascondila immediatamente
        hwnd_console = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd_console:
            ctypes.windll.user32.ShowWindow(hwnd_console, 0)  # SW_HIDE
        ctypes.windll.kernel32.FreeConsole()
    except Exception:
        pass

# Aggiungi la root del progetto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from ui.main_window import MainWindow
from themes.dark_theme import DARK_QSS


def main():
    # Abilita High DPI
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("PyMRemoteNG")
    app.setOrganizationName("PyMRemoteNG")

    # Tema dark globale
    app.setStyleSheet(DARK_QSS)

    # Font di default più grande
    font = QFont("Segoe UI", 12)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
