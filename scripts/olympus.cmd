@echo off
setlocal
set "PYTHONDONTWRITEBYTECODE=1"
if not defined OLYMPUS_PYTHON set "OLYMPUS_PYTHON=python3.11"
"%OLYMPUS_PYTHON%" -B "%~dp0olympus_cli.py" %*
exit /b %errorlevel%
