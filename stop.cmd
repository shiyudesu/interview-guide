@echo off
setlocal

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop.ps1"
set "script_exit_code=%ERRORLEVEL%"

echo.
if not "%script_exit_code%"=="0" (
  echo Shutdown failed. Review the messages above.
) else (
  echo You can close this window.
)
pause
exit /b %script_exit_code%
