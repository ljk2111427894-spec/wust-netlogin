@echo off
cd /d "%~dp0"
echo ========================================================
echo     Campus Network Auto-Reconnect Daemon (59.68.177.9)
echo ========================================================
echo Launching CampusNetLogin into system status bar tray...
echo.
if exist "CampusNetLogin.exe" (
    start "" "CampusNetLogin.exe" --tray
    exit /b 0
)
where pythonw >nul 2>nul
if %errorlevel% equ 0 (
    start "" pythonw main.py --tray
    exit /b 0
)
where python >nul 2>nul
if %errorlevel% equ 0 (
    start "" python main.py --tray
    exit /b 0
)
pause
