@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo Install first with INSTALL_WINDOWS.cmd & pause & exit /b 1)
".venv\Scripts\python.exe" -m pytest -q
pause
