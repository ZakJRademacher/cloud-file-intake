@echo off
cd /d "%~dp0"
set "INTAKE_PYTHON="
if exist "%LOCALAPPDATA%\cloud-file-intake-tools\python-path.txt" set /p INTAKE_PYTHON=<"%LOCALAPPDATA%\cloud-file-intake-tools\python-path.txt"
if defined INTAKE_PYTHON (
  "%INTAKE_PYTHON%" -m src.local_web --open-browser
) else (
  py -3 -m src.local_web --open-browser
)
if errorlevel 1 (
  echo Install Python 3.12 or configure the project Python executable. See README.md.
  pause
)
