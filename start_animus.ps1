# Animus Smart Room One-Click Startup Script (PowerShell)
Write-Host "=====================================================" -ForegroundColor Cyan
Write-Host "   Starting Animus Smart Room Intelligence Daemon   " -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan

# 1. Dynamic Auto-Discovery & ADB Connect
Write-Host "`n[1/3] Auto-discovering hardware & connecting ADB targets..." -ForegroundColor Yellow
python scripts/discover_and_connect_adb.py

# 2. Check Python Environment & Start Daemon
Write-Host "`n[2/3] Starting Animus Daemon on port 8095..." -ForegroundColor Yellow
$daemonProcess = Start-Process python -ArgumentList "server/music_daemon/main.py" -PassThru

# 3. Wait for readiness and launch Interactive Console
Write-Host "`n[3/3] Waiting for server readiness..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host "`n[READY] Launching Animus Interactive Console..." -ForegroundColor Green
python animus_console.py
