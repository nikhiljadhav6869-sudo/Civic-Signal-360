@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python environment missing. Follow the README setup instructions first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" scripts\check_readiness.py
set "CIVIC_CHECK_EXIT=%ERRORLEVEL%"
pause
exit /b %CIVIC_CHECK_EXIT%
