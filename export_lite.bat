@echo off
rem Builds the "Lite" package (source code + INSTALLATION.txt only) as export\CoreMonitor_Lite_<date>.zip
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\export.ps1" -Variante Lite
pause
