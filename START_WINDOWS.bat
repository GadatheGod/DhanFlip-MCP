@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo First launch - installing DhanFlip dependencies...
 call "%~dp0INSTALL_WINDOWS.cmd"
 if not exist ".venv\Scripts\python.exe" exit /b 1
)
".venv\Scripts\python.exe" -m dhanflip gui
if errorlevel 1 (
 echo DhanFlip stopped with an error. Run RUN_TESTS.bat for diagnostics.
 pause
)
