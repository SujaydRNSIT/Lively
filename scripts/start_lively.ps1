# PowerShell 1-Click Startup for Lively Real-Time Voice AI Sales Agent
# Usage: powershell -ExecutionPolicy Bypass -File .\scripts\start_lively.ps1

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $ScriptDir

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "            LIVELY - REAL-TIME VOICE AI SALES AGENT         " -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 1. Check Python Environment
$PythonExe = ""
if (Test-Path "$ScriptDir\.venv\Scripts\python.exe") {
    $PythonExe = "$ScriptDir\.venv\Scripts\python.exe"
} elseif (Test-Path "$ScriptDir\venv\Scripts\python.exe") {
    $PythonExe = "$ScriptDir\venv\Scripts\python.exe"
} else {
    $PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
}

if (-not $PythonExe) {
    Write-Host "[ERROR] Python not found. Please run install.bat or create a venv." -ForegroundColor Red
    exit 1
}

# 2. Check Node & Frontend
if (-not (Test-Path "$ScriptDir\frontend\node_modules")) {
    Write-Host "[*] Installing frontend dependencies (npm install)..." -ForegroundColor Yellow
    npm --prefix frontend install
}

# 3. Check .env
if (-not (Test-Path "$ScriptDir\.env")) {
    if (Test-Path "$ScriptDir\.env.example") {
        Copy-Item "$ScriptDir\.env.example" "$ScriptDir\.env"
        Write-Host "[!] Created .env from .env.example. Please insert your AGORA credentials." -ForegroundColor Yellow
    }
}
Copy-Item "$ScriptDir\.env" "$ScriptDir\backend\.env" -Force

# 4. Launch with Python launcher (Handles free ports, Cloudflare tunnel, backend, and frontend)
Write-Host "[*] Launching Lively System..." -ForegroundColor Green
& $PythonExe -u "$ScriptDir\scripts\launcher.py" $args
