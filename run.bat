@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Lively Voice AI

set "PYTHON_EXE="
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "venv\Scripts\python.exe" set "PYTHON_EXE=venv\Scripts\python.exe"

if not defined PYTHON_EXE goto :setup
if not exist "frontend\node_modules" goto :setup
goto :config

:setup
echo Lively dependencies are not installed yet. Running setup...
call install.bat --no-pause
if errorlevel 1 (
    echo.
    echo [ERROR] Setup failed. Review the messages above.
    pause
    exit /b 1
)
if exist ".venv\Scripts\python.exe" set "PYTHON_EXE=.venv\Scripts\python.exe"
if not defined PYTHON_EXE if exist "venv\Scripts\python.exe" set "PYTHON_EXE=venv\Scripts\python.exe"

:config
if not exist ".env" (
    echo [ERROR] .env is missing. Run install.bat first.
    pause
    exit /b 1
)

set "MISSING_CONFIG="
for %%K in (AGORA_APP_ID AGORA_APP_CERTIFICATE AGORA_REST_KEY AGORA_REST_SECRET) do (
    findstr /r /c:"^%%K=..*$" ".env" >nul || set "MISSING_CONFIG=1"
)
if defined MISSING_CONFIG (
    echo [ERROR] Add AGORA_APP_ID, AGORA_APP_CERTIFICATE, AGORA_REST_KEY, and AGORA_REST_SECRET to .env.
    echo Your teammate should use their own Agora project credentials; do not commit .env.
    pause
    exit /b 1
)

if not exist "cloudflared.exe" (
    echo [ERROR] cloudflared.exe is missing. Run install.bat again while connected to the internet.
    pause
    exit /b 1
)

copy /y ".env" "backend\.env" >nul

echo [*] Automatically clearing any previous port usages or background tasks...
"%PYTHON_EXE%" scripts\free_ports.py

"%PYTHON_EXE%" -u scripts\launcher.py %*
set "EXIT_CODE=%errorlevel%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Lively stopped with exit code %EXIT_CODE%.
    pause
)
exit /b %EXIT_CODE%

