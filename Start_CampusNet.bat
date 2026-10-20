@echo off
cd /d "%~dp0"
echo Starting Campus Network Auto Login...
if exist "CampusNetLogin.exe" (
    start "" "CampusNetLogin.exe"
    exit /b 0
)
where pythonw >nul 2>nul
if %errorlevel% equ 0 (
    start "" pythonw main.py
    exit /b 0
)
where python >nul 2>nul
if %errorlevel% equ 0 (
    start "" python main.py
    exit /b 0
)
echo [Error] Python or CampusNetLogin.exe not found!
pause
