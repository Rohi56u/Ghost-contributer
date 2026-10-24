@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\ghost.exe" goto missing
echo Keep your local Ollama server running for real inference.
echo Open the complete dashboard URL below, including its token.
".venv\Scripts\ghost.exe" dashboard
goto end
:missing
echo Run setup-windows.bat once before starting the dashboard.
:end
pause
