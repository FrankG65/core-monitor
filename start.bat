@echo off
rem Start Core Monitor (Kern-Monitor).
rem  - Package "Full" (Komplett): embedded Python and finished programs are included -> nothing to install or build.
rem  - Package "Lite" (Klein) / source folder: installed Python; packages via pip, comparison programs are built
rem    as far as the tools are available (missing tools -> these computation methods are only greyed out in the list).
setlocal
cd /d "%~dp0"
if not defined PORT set PORT=8000

if exist "%~dp0python\python.exe" goto komplett
set "PY=python"
where python >nul 2>&1 || goto nopython
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)" || goto oldpython
python -m pip install -q -r requirements.txt || goto pipfail
rem numba is optional (faster computation method); without numba numpy is used
python -m pip install -q numba || echo numba not installed - Mandelbrot runs with numpy (numba nicht installiert)
rem comparison programs only if the tools are present (see INSTALLATION.txt)
where dotnet >nul 2>&1 && dotnet build csharp\MandelBench -c Release -o csharp\bin --nologo -v q
set CARGO=cargo
where cargo >nul 2>&1 || set CARGO="%USERPROFILE%\.cargo\bin\cargo.exe"
if exist %CARGO% (pushd rust\mandelbench & %CARGO% build --release --quiet & popd) else (where cargo >nul 2>&1 && (pushd rust\mandelbench & cargo build --release --quiet & popd))
call native\build.bat
goto run

:komplett
set "PY=%~dp0python\python.exe"
echo Package "Full" (Komplett): using embedded Python and finished programs.

:run
rem No fixed browser call: the server opens a tab only if no page is open.
set OPEN_BROWSER=1
"%PY%" server.py
goto :eof

:nopython
echo Python not found. Please install Python 3.11 or newer (see INSTALLATION.txt).
echo (Python wurde nicht gefunden. Bitte Python 3.11 oder neuer installieren.)
pause
exit /b 1
:oldpython
echo Python is too old. Version 3.11 or newer is required (see INSTALLATION.txt).
echo (Python ist zu alt. Benoetigt wird Version 3.11 oder neuer.)
pause
exit /b 1
:pipfail
echo The Python packages could not be installed (internet connection?). See INSTALLATION.txt.
echo (Die Python-Pakete konnten nicht installiert werden - Internetverbindung?)
pause
exit /b 1
