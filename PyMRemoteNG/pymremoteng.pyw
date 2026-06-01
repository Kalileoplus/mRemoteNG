"""
Launcher senza console - usa pythonw.exe automaticamente.
Doppio click su questo file per avviare senza CMD nero.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from main import main
main()
