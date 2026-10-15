@echo off
setlocal
cd /d "%~dp0"
set "PORTABLE_EXE=%CD%\dist\portable-0.23.0\AzaleaCore MPQ Studio\AzaleaCore MPQ Studio.exe"
if exist "%PORTABLE_EXE%" (
    start "" "%PORTABLE_EXE%"
    exit /b 0
)
set "PYTHONPATH=%CD%\src"
pythonw -m azaleacore_mpq_studio
if errorlevel 1 pause
