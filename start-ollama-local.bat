@echo off
setlocal
echo Start your existing Ollama installation in local-only mode.
echo First quit the Ollama tray application if it is already running.
echo This preserves your model directory and does not download models.
where ollama >nul 2>nul
if errorlevel 1 goto missing
set "OLLAMA_NO_CLOUD=1"
set "OLLAMA_HOST=127.0.0.1:11434"
ollama serve
if errorlevel 1 echo If port 11434 is in use, quit the old Ollama tray instance and retry.
goto end
:missing
echo Ollama was not found on PATH. Open a new terminal after installing Ollama.
:end
pause
