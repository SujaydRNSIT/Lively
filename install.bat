@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title Lively - Setup

set "NO_PAUSE=0"
set "SETUP_EXIT=0"
if /i "%~1"=="--no-pause" set "NO_PAUSE=1"

echo ============================================================
echo                    LIVELY - TEAM SETUP
echo ============================================================
echo.

rem Prefer a real installed Python over the Microsoft Store alias.
set "PYTHON_EXE="
for %%V in (313 312 311 310) do (
    if not defined PYTHON_EXE if exist "%LocalAppData%\Programs\Python\Python%%V\python.exe" set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python%%V\python.exe"
)
for %%V in (313 312 311 310) do (
    if not defined PYTHON_EXE if exist "%ProgramFiles%\Python%%V\python.exe" set "PYTHON_EXE=%ProgramFiles%\Python%%V\python.exe"
)
if not defined PYTHON_EXE (
    for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYTHON_EXE set "PYTHON_EXE=%%P"
)
if not defined PYTHON_EXE (
    echo [ERROR] Python 3.10+ is required.
    echo Install it from https://www.python.org/downloads/windows/ and select "Add Python to PATH".
    goto :failure
)
"%PYTHON_EXE%" --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Found Python at "%PYTHON_EXE%", but Windows cannot run it.
    goto :failure
)

node --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Node.js 18+ is required. Install it from https://nodejs.org/.
    goto :failure
)
for /f "tokens=1 delims=." %%A in ('node --version') do set "NODE_MAJOR=%%A"
set "NODE_MAJOR=!NODE_MAJOR:v=!"
if !NODE_MAJOR! LSS 18 (
    echo [ERROR] Node.js 18+ is required; found Node !NODE_MAJOR!.
    goto :failure
)
call npm.cmd --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] npm is unavailable. Reinstall Node.js, then rerun this script.
    goto :failure
)

echo [1/5] Creating project-local Python environment...
if not exist ".venv\Scripts\python.exe" (
    "%PYTHON_EXE%" -m venv .venv
    if errorlevel 1 goto :failure
)

echo [2/5] Installing core backend packages. This may take a few minutes the first time...
.venv\Scripts\python.exe -m pip install --disable-pip-version-check --upgrade pip
if errorlevel 1 goto :failure
.venv\Scripts\python.exe -m pip install --prefer-binary -r backend\requirements.txt
if errorlevel 1 goto :failure
.venv\Scripts\python.exe -m pip check
if errorlevel 1 goto :failure

echo [3/5] Installing frontend packages from the lockfile...
call npm.cmd ci --prefix frontend
if errorlevel 1 goto :failure

echo [4/5] Preparing local configuration...
if not exist ".env" (
    copy /y ".env.example" ".env" >nul
    echo Created .env from .env.example.
    echo Add your Agora credentials before running the voice agent.
) else (
    echo Existing .env preserved.
)
copy /y ".env" "backend\.env" >nul

findstr /r /c:"^PINECONE_API_KEY=..*$" ".env" >nul
if not errorlevel 1 (
    echo Installing optional Pinecone semantic RAG packages...
    .venv\Scripts\python.exe -m pip install --prefer-binary -r backend\requirements-pinecone.txt
    if errorlevel 1 goto :failure
) else (
    echo Using built-in in-memory RAG. Add PINECONE_API_KEY later to enable semantic RAG.
)

echo [5/5] Checking Cloudflare tunnel helper...
if not exist "cloudflared.exe" (
    where curl.exe >nul 2>&1
    if not errorlevel 1 (
        echo Downloading cloudflared.exe...
        curl.exe -L --fail --retry 2 -o cloudflared.exe https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
    )
)
if not exist "cloudflared.exe" (
    echo [WARNING] cloudflared.exe could not be downloaded.
    echo Download it from https://github.com/cloudflare/cloudflared/releases/latest and place it in this folder.
) else (
    cloudflared.exe --version >nul 2>&1
    if errorlevel 1 (
        echo [WARNING] cloudflared.exe is present but could not be started.
    ) else (
        echo cloudflared is ready.
    )
)

echo.
echo Setup complete.
echo Next: add credentials to .env, then double-click run.bat.
goto :finish

:failure
echo.
echo Setup did not complete. Fix the error above and run install.bat again.
set "SETUP_EXIT=1"

:finish
if "%NO_PAUSE%"=="0" pause
exit /b %SETUP_EXIT%
