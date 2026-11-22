@echo off
echo ==================================================================
echo Running Automated Test Suite (93 Tests across 12 Modules)...
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

%PYTHON_EXE% -m pytest tests -v
pause
