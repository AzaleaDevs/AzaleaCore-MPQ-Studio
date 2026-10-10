@echo off
setlocal
cd /d "%~dp0"
set "PYTHONPATH=%CD%\src"
python -m azaleacore_mpq_studio
if errorlevel 1 pause
