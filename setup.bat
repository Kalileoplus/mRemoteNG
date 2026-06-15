@echo off
setlocal
title Nexus - Setup

echo.
echo  =========================================
echo   Nexus  -  Installazione dipendenze
echo  =========================================
echo.

:: Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRORE] Python non trovato.
    echo.
    echo  Scarica Python 3.10 o superiore da:
    echo  https://www.python.org/downloads/
    echo.
    echo  Durante l'installazione spunta "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo  Python trovato:
python --version
echo.

echo [1/1] Installo dipendenze...
pip install -r "%~dp0PyMRemoteNG\requirements.txt"
if errorlevel 1 (
    echo.
    echo [ERRORE] Installazione dipendenze fallita.
    echo  Prova a rieseguire come Amministratore.
    pause
    exit /b 1
)

echo.
echo  =========================================
echo   Setup completato!
echo  =========================================
echo.
echo  Per avviare Nexus usa:  launcher.bat
echo.
pause
