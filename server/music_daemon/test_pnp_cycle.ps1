
# Test cycling the MEDIA PnP endpoint
$a2dpDevice = Get-PnpDevice | Where-Object { $_.InstanceId -like "BTHENUM\{0000110B-0000-1000-8000-00805F9B34FB}*541589DCA579*" }
Write-Output "Found A2DP PnP Device: $($a2dpDevice.FriendlyName) ($($a2dpDevice.InstanceId))"

# Check if we can disable and re-enable to trigger Windows A2DP connect
try {
    Write-Output "Disabling A2DP node..."
    Disable-PnpDevice -InstanceId $a2dpDevice.InstanceId -Confirm:$false -ErrorAction Stop
    Start-Sleep -Milliseconds 500
    Write-Output "Enabling A2DP node..."
    Enable-PnpDevice -InstanceId $a2dpDevice.InstanceId -Confirm:$false -ErrorAction Stop
    Start-Sleep -Seconds 2
    Write-Output "A2DP Node cycled successfully."
} catch {
    Write-Output "PnP toggle error (requires Admin): $($_.Exception.Message)"
}

$pnp = Get-PnpDevice -InstanceId "SWD\MMDEVAPI\{0.0.0.00000000}.{8C260B12-CA22-4DF8-B71F-DD78EBA2CA15}" -ErrorAction SilentlyContinue
Write-Output "Audio Endpoint Present: $($pnp.Present)"
