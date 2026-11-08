@echo off
rem Builds the "Full" package (runs without installation and without internet) as export\CoreMonitor_Full_<date>.zip
rem Requires on THIS PC: Python 3.11, internet (once, for the Python download), .NET SDK, Rust, Visual Studio C++.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0tools\export.ps1" -Variante Full
pause
