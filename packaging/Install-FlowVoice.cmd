@echo off
rem Double-click to install Flow Voice for the current user (no administrator rights needed).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-FlowVoice.ps1" %*
echo.
pause
