@echo off
setlocal
cd /d "%~dp0"
echo Ghost Contributor - real Ollama setup
echo Your installed Ollama models will be listed. No models are downloaded.
where git >nul 2>nul
if errorlevel 1 goto missinggit
if exist ".venv\Scripts\python.exe" goto install
py -3.12 -c "import sys" >nul 2>nul
if not errorlevel 1 goto python312
py -3.13 -c "import sys" >nul 2>nul
if not errorlevel 1 goto python313
py -3.11 -c "import sys" >nul 2>nul
if not errorlevel 1 goto python311
python -c "import sys; sys.exit(0 if (3,11) <= sys.version_info[:2] < (3,14) else 1)" >nul 2>nul
if errorlevel 1 goto missingpython
python -m venv .venv
goto envready
:python312
py -3.12 -m venv .venv
goto envready
:python313
py -3.13 -m venv .venv
goto envready
:python311
py -3.11 -m venv .venv
:envready
if errorlevel 1 goto failed
:install
".venv\Scripts\python.exe" -m pip install -e .
if errorlevel 1 goto failed
".venv\Scripts\ghost.exe" setup
if errorlevel 1 goto failed
echo Open the complete dashboard URL printed below, including its token.
".venv\Scripts\ghost.exe" dashboard
goto end
:missinggit
echo Install Git for Windows and run this file again.
goto end
:missingpython
echo Install Python 3.11, 3.12 or 3.13. Python 3.12 is recommended for this release.
goto end
:failed
echo Setup stopped. Read the error above and START-HERE-WINDOWS.md.
echo If Ollama is unavailable, run start-ollama-local.bat first.
echo If this repo is already registered, use start-ghost.bat.
:end
pause
