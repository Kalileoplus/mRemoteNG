@echo off
setlocal
title Nexus - Disinstallazione

echo.
echo  ============================================================
echo    Nexus  -  Disinstallazione
echo  ============================================================
echo.
set /p "CONFIRM=   Sei sicuro di voler disinstallare Nexus? [S/N]:  "
if /i not "%CONFIRM%"=="S" exit /b 0

echo.
echo  Rimozione collegamenti...
del "%USERPROFILE%\Desktop\Nexus.lnk" >nul 2>&1
rmdir /s /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Nexus" >nul 2>&1

echo  Rimozione voce da Programmi installati...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\Nexus" /f >nul 2>&1

echo  Rimozione dati applicazione...
rmdir /s /q "%APPDATA%\Nexus" >nul 2>&1

echo.
echo  ============================================================
echo    Nexus disinstallato correttamente.
echo  ============================================================
echo.
pause
