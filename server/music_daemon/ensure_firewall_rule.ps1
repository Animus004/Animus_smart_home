# Ensure Port 8095 TCP is open for Animus Smart Room Mobile Clients
$ruleName = "Animus PC Daemon (Port 8095)"
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue

if (-not $existing) {
    try {
        New-NetFirewallRule -DisplayName $ruleName `
            -Direction Inbound `
            -LocalPort 8095 `
            -Protocol TCP `
            -Action Allow `
            -Profile Any `
            -Description "Allows mobile devices on LAN to connect to Animus Smart Room Intelligence Daemon"
        Write-Host "[FIREWALL] Successfully created inbound rule for port 8095." -ForegroundColor Green
    } catch {
        Write-Host "[FIREWALL] Error creating rule: $_" -ForegroundColor Red
    }
} else {
    Write-Host "[FIREWALL] Inbound rule for port 8095 already active." -ForegroundColor Cyan
}
