@echo off
setlocal

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start.ps1"
set "script_exit_code=%ERRORLEVEL%"

echo.
if not "%script_exit_code%"=="0" (
  echo Startup failed. Review the messages above.
) else (
  echo You can close this window. Services will keep running in the background.
)
pause
exit /b %script_exit_code%
