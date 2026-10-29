@echo off
cd /d "%~dp0"
set "INTAKE_WORKBENCH_PYTHON="
if exist "%LOCALAPPDATA%\cloud-file-intake-tools\python-path.txt" set /p INTAKE_WORKBENCH_PYTHON=<"%LOCALAPPDATA%\cloud-file-intake-tools\python-path.txt"
if defined INTAKE_WORKBENCH_PYTHON (
  "%INTAKE_WORKBENCH_PYTHON%" -m src.local_web --port 8803 --workspace --open-browser
) else (
  py -3 -m src.local_web --port 8803 --workspace --open-browser
)
if errorlevel 1 (
  echo If the workbench is already running, open http://127.0.0.1:8803/workspace
  echo Otherwise install Python 3.12 or configure the project Python executable. See README.md.
  pause
)
