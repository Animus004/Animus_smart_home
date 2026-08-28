# ==============================================================================
# Animus Smart Room — Windows Automatic Startup Installer
# Registers the Animus Intelligence Daemon in Windows Task Scheduler
# to automatically wake up and run when Windows boots up / power is restored.
# ==============================================================================

param(
    [switch]$Uninstall,
    [switch]$Status,
    [string]$TaskName = "AnimusSmartRoomDaemon",
    [string]$WorkspaceRoot = "d:\AnimusSmartRoom"
)

$PythonExe = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) {
    $PythonExe = "python.exe"
}

if ($Status) {
    Write-Host "Checking Task Scheduler status for '$TaskName'..." -ForegroundColor Cyan
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        Write-Host "[INSTALLED] Task '$TaskName' is registered." -ForegroundColor Green
        Write-Host "State: $($task.State)"
        Write-Host "Trigger: $($task.Triggers | Out-String)"
    } else {
        Write-Host "[NOT FOUND] Task '$TaskName' is not currently registered in Task Scheduler." -ForegroundColor Yellow
    }
    exit 0
}

if ($Uninstall) {
    Write-Host "Unregistering '$TaskName' from Task Scheduler..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "[OK] Task '$TaskName' unregistered successfully." -ForegroundColor Green
    exit 0
}

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "   Animus Smart Room Auto-Startup Service Installer              " -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan

# 1. Verify workspace exists
if (-not (Test-Path "$WorkspaceRoot\server\music_daemon\main.py")) {
    Write-Error "Could not locate server/music_daemon/main.py at $WorkspaceRoot."
    exit 1
}

# 2. Define Action
$Action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument "server/music_daemon/main.py" `
    -WorkingDirectory $WorkspaceRoot

# 3. Define Triggers (At System Startup and At User Logon for resilience)
$TriggerStartup = New-ScheduledTaskTrigger -AtStartup
$TriggerLogon = New-ScheduledTaskTrigger -AtLogOn

# 4. Define Settings (Restart on failure, run indefinitely, don't stop if battery/network drops)
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Days 365) `
    -RestartCount 5 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable

# 5. Define Principal (Highest RunLevel)
$Principal = New-ScheduledTaskPrincipal `
    -UserId "$env:USERDOMAIN\$env:USERNAME" `
    -LogonType Interactive `
    -RunLevel Highest

Write-Host "[1/2] Registering scheduled task '$TaskName'..." -ForegroundColor Yellow

# Remove old task if exists
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

# Register new scheduled task
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger @($TriggerStartup, $TriggerLogon) `
    -Settings $Settings `
    -Principal $Principal `
    -Description "Animus Smart Room Intelligence Server and Hardware Daemon (Auto-Start on Boot)"

Write-Host "[2/2] Task registered successfully!" -ForegroundColor Green
Write-Host "`n[SUCCESS] Animus Smart Room will now automatically wake up and start when Windows boots up." -ForegroundColor Cyan
Write-Host "To test: Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Gray
Write-Host "To check status: powershell -File scripts/install_animus_service.ps1 -Status" -ForegroundColor Gray
Write-Host "To uninstall: powershell -File scripts/install_animus_service.ps1 -Uninstall" -ForegroundColor Gray
