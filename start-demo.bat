@echo off
setlocal
cd /d "%~dp0"
echo Ghost Contributor - local fixture demo
echo Requires Python 3.12 and Git. No AI model is downloaded.
where git >nul 2>nul
if errorlevel 1 goto missinggit
if not exist ".venv\Scripts\python.exe" py -3.12 -m venv .venv
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install .
if errorlevel 1 goto failed
if not exist "ghost-demo\state\policy.toml" ".venv\Scripts\ghost.exe" demo --directory ghost-demo
if errorlevel 1 goto failed
".venv\Scripts\ghost.exe" --home "ghost-demo\state" dashboard
goto end
:missinggit
echo Install Git for Windows, then run this file again.
goto end
:failed
echo Setup stopped. Check the error above. Python 3.12 must be installed.
:end
pause
