@echo off
setlocal EnableDelayedExpansion
title Nexus - Installazione

set "APP_DIR=%~dp0"
set "APP_DIR=%APP_DIR:~0,-1%"
set "MAIN_PY=%APP_DIR%\PyMRemoteNG\main.py"
set "ICON_ICO=%APP_DIR%\PyMRemoteNG\icon.ico"
set "REG_KEY=HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\Nexus"

echo.
echo  ============================================================
echo    Nexus  -  Installazione
echo  ============================================================
echo.

:: ── 1. Verifica Python ────────────────────────────────────────
echo  [1/4]  Verifica Python...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  [ERRORE] Python non trovato sul sistema.
    echo.
    echo  Scarica Python 3.10 o superiore da:
    echo     https://www.python.org/downloads/
    echo.
    echo  IMPORTANTE: durante l'installazione spunta
    echo     "Add Python to PATH"
    echo.
    pause
    exit /b 1
)
for /f "tokens=*" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo         OK  ^(!PYVER!^)

:: ── 2. Dipendenze pip ─────────────────────────────────────────
echo  [2/4]  Installo dipendenze Python...
pip install -r "%APP_DIR%\PyMRemoteNG\requirements.txt" -q
if errorlevel 1 (
    echo.
    echo  [ERRORE] Installazione dipendenze fallita.
    echo  Prova a rieseguire come Amministratore.
    echo.
    pause
    exit /b 1
)
echo         OK

:: ── 3. Icona ─────────────────────────────────────────────────
echo  [3/4]  Genero icona...
pip show pillow >nul 2>&1 || pip install pillow -q
python "%APP_DIR%\create_icon.py" >nul 2>&1
echo         OK

:: ── 4. Shortcuts + registro ───────────────────────────────────
echo  [4/4]  Creo collegamenti e registro app...

:: Trova pythonw.exe accanto a python.exe
for /f "delims=" %%p in ('where python 2^>nul') do set PYTHON_EXE=%%p & goto :found_python
:found_python
set "PYTHONW_EXE=!PYTHON_EXE:python.exe=pythonw.exe!"
if not exist "!PYTHONW_EXE!" set "PYTHONW_EXE=!PYTHON_EXE!"

:: Scrive uno script PowerShell temporaneo per i collegamenti
set "PS_TMP=%TEMP%\nexus_install.ps1"
(
echo $pythonw  = '%PYTHONW_EXE:\=\\%'
echo $mainPy   = '%MAIN_PY:\=\\%'
echo $workDir  = '%APP_DIR:\=\\%\PyMRemoteNG'
echo $icon     = '%ICON_ICO:\=\\%'
echo $ws       = New-Object -ComObject WScript.Shell
echo.
echo # Collegamento Desktop
echo $lnk = $ws.CreateShortcut^([Environment]::GetFolderPath^('Desktop'^) + '\Nexus.lnk'^)
echo $lnk.TargetPath       = $pythonw
echo $lnk.Arguments        = "`"$mainPy`""
echo $lnk.WorkingDirectory = $workDir
echo $lnk.IconLocation     = $icon
echo $lnk.Description      = 'Nexus Remote Manager'
echo $lnk.Save^(^)
echo.
echo # Collegamento Menu Start
echo $smDir = [Environment]::GetFolderPath^('StartMenu'^) + '\Programs\Nexus'
echo if ^(-not ^(Test-Path $smDir^)^) { New-Item -ItemType Directory $smDir ^| Out-Null }
echo $sm = $ws.CreateShortcut^($smDir + '\Nexus.lnk'^)
echo $sm.TargetPath       = $pythonw
echo $sm.Arguments        = "`"$mainPy`""
echo $sm.WorkingDirectory = $workDir
echo $sm.IconLocation     = $icon
echo $sm.Description      = 'Nexus Remote Manager'
echo $sm.Save^(^)
echo.
echo # Collegamento Menu Start - Disinstalla
echo $un = $ws.CreateShortcut^($smDir + '\Disinstalla Nexus.lnk'^)
echo $un.TargetPath       = '%APP_DIR:\=\\%\uninstall.bat'
echo $un.WorkingDirectory = '%APP_DIR:\=\\%'
echo $un.Description      = 'Disinstalla Nexus'
echo $un.Save^(^)
) > "%PS_TMP%"

powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_TMP%" >nul 2>&1
del "%PS_TMP%" >nul 2>&1

:: Registra in "Programmi installati" (HKCU, no admin richiesto)
reg add "%REG_KEY%" /v "DisplayName"     /t REG_SZ    /d "Nexus"                        /f >nul
reg add "%REG_KEY%" /v "DisplayVersion"  /t REG_SZ    /d "1.0.0"                        /f >nul
reg add "%REG_KEY%" /v "Publisher"       /t REG_SZ    /d "Kalileoplus"                  /f >nul
reg add "%REG_KEY%" /v "InstallLocation" /t REG_SZ    /d "%APP_DIR%"                    /f >nul
reg add "%REG_KEY%" /v "DisplayIcon"     /t REG_SZ    /d "%ICON_ICO%"                   /f >nul
reg add "%REG_KEY%" /v "UninstallString" /t REG_SZ    /d "%APP_DIR%\uninstall.bat"      /f >nul
reg add "%REG_KEY%" /v "NoModify"        /t REG_DWORD /d 1                              /f >nul
reg add "%REG_KEY%" /v "NoRepair"        /t REG_DWORD /d 1                              /f >nul
echo         OK

echo.
echo  ============================================================
echo    Installazione completata!
echo  ============================================================
echo.
echo    Collegamento Desktop:    Nexus
echo    Menu Start:              Tutti i programmi ^> Nexus
echo    Disinstalla:             Pannello di controllo ^> Programmi
echo.
set /p "LAUNCH=   Avviare Nexus adesso? [S/N]:  "
if /i "!LAUNCH!"=="S" (
    cd /d "%APP_DIR%\PyMRemoteNG"
    start "" "!PYTHONW_EXE!" "%MAIN_PY%"
)
echo.
pause
