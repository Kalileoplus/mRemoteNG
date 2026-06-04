@echo off
setlocal EnableDelayedExpansion
title PyMRemoteNG - Build ^& Package

echo.
echo  =========================================
echo   PyMRemoteNG  -  Build EXE + Installer
echo  =========================================
echo.

:: -------------------------------------------------------
:: 1. Dipendenze Python
:: -------------------------------------------------------
echo [1/5] Installo dipendenze Python...
pip install -r "%~dp0PyMRemoteNG\requirements.txt" -q
if errorlevel 1 ( echo [ERRORE] Installazione dipendenze fallita. & pause & exit /b 1 )
pip show pillow      >nul 2>&1 || pip install pillow      -q
pip show pyinstaller >nul 2>&1 || pip install pyinstaller -q
echo       OK

:: -------------------------------------------------------
:: 2. Genera icona
:: -------------------------------------------------------
echo [2/5] Genero icona...
python "%~dp0create_icon.py"
if errorlevel 1 ( echo [ERRORE] Generazione icona fallita. & pause & exit /b 1 )

:: -------------------------------------------------------
:: 3. Build EXE con PyInstaller
:: -------------------------------------------------------
echo [3/5] Build EXE con PyInstaller...
cd /d "%~dp0PyMRemoteNG"
if exist dist  rmdir /s /q dist
if exist build rmdir /s /q build

pyinstaller pymremoteng.spec --noconfirm
if errorlevel 1 ( echo [ERRORE] Build PyInstaller fallita. & pause & exit /b 1 )
cd /d "%~dp0"
echo       OK

:: -------------------------------------------------------
:: 4. Copia cartella shared nel dist
:: -------------------------------------------------------
echo [4/5] Copio shared nel pacchetto...
if not exist "PyMRemoteNG\dist\PyMRemoteNG\shared" mkdir "PyMRemoteNG\dist\PyMRemoteNG\shared"
copy /Y "shared\confCons.xml.template" "PyMRemoteNG\dist\PyMRemoteNG\shared\" >nul
echo       OK

:: -------------------------------------------------------
:: 5. Compile installer con Inno Setup
:: -------------------------------------------------------
echo [5/5] Creo installer con Inno Setup...

:: Cerca ISCC.exe nelle posizioni standard
set ISCC=
for %%P in (
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
    "C:\Program Files\Inno Setup 6\ISCC.exe"
    "C:\Program Files (x86)\Inno Setup 5\ISCC.exe"
    "C:\Program Files\Inno Setup 5\ISCC.exe"
) do (
    if exist %%P set ISCC=%%P
)

if "!ISCC!"=="" (
    echo.
    echo  [ATTENZIONE] Inno Setup non trovato.
    echo  Scaricalo da: https://jrsoftware.org/isdl.php
    echo  Poi rilancia questo script.
    echo.
    echo  L'EXE e' comunque pronto in:
    echo  PyMRemoteNG\dist\PyMRemoteNG\PyMRemoteNG.exe
    echo.
    pause
    exit /b 0
)

if not exist dist mkdir dist
"!ISCC!" installer.iss
if errorlevel 1 ( echo [ERRORE] Compilazione installer fallita. & pause & exit /b 1 )

echo.
echo  =========================================
echo   Build completata con successo!
echo  =========================================
echo.
echo   Installer: dist\PyMRemoteNG_Setup.exe
echo   EXE raw:   PyMRemoteNG\dist\PyMRemoteNG\PyMRemoteNG.exe
echo.
pause >nul
explorer "dist"
