@echo off
echo ==================================================================
echo Starting Smart Electricity Wastage Detection & Intelligence System
echo ==================================================================

REM Determine project root
set "SCRIPT_DIR=%~dp0"
cd /d "%SCRIPT_DIR%.."

REM Check virtualenv
if exist "..\.venv\Scripts\python.exe" (
    set PYTHON_EXE=..\.venv\Scripts\python.exe
) else if exist ".venv\Scripts\python.exe" (
    set PYTHON_EXE=.venv\Scripts\python.exe
) else (
    set PYTHON_EXE=python
)

echo Using Python: %PYTHON_EXE%
%PYTHON_EXE% scripts\start_app.py
pause
