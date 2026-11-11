@echo off
setlocal DisableDelayedExpansion
set "PYTHONDONTWRITEBYTECODE=1"
set "OLYMPUS_ROOT=%~dp0.."
if not exist "%OLYMPUS_ROOT%\current.txt" goto checkout
for /f "usebackq delims=" %%V in ("%OLYMPUS_ROOT%\current.txt") do set "OLYMPUS_VERSION=%%V"
if not defined OLYMPUS_VERSION goto invalid_install
set "OLYMPUS_ENTRY=%OLYMPUS_ROOT%\versions\%OLYMPUS_VERSION%\scripts\olympus_cli.py"
if not exist "%OLYMPUS_ENTRY%" goto missing_release
goto select_python

:checkout
set "OLYMPUS_ENTRY=%~dp0olympus_cli.py"
if not exist "%OLYMPUS_ENTRY%" goto missing_checkout

:select_python
if defined OLYMPUS_PYTHON goto use_custom_python
where py >nul 2>nul
if errorlevel 1 goto use_python
(goto) 2>nul & py -3 -B "%OLYMPUS_ENTRY%" %*

:use_python
where python >nul 2>nul
if errorlevel 1 goto missing_python
(goto) 2>nul & python -B "%OLYMPUS_ENTRY%" %*

:use_custom_python
(goto) 2>nul & "%OLYMPUS_PYTHON%" -B "%OLYMPUS_ENTRY%" %*

:invalid_install
echo Olympus CLI is not installed correctly. Run the Olympus installer again. 1>&2
exit /b 3

:missing_release
echo Olympus CLI release files are missing. Run olympus doctor or reinstall. 1>&2
exit /b 3

:missing_checkout
echo Olympus CLI checkout entrypoint is missing. 1>&2
exit /b 3

:missing_python
echo Olympus requires Python 3.11 or newer. 1>&2
exit /b 3
