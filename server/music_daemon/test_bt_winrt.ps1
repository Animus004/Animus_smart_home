
# Connect stream socket using HostName and ServiceName
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.IsGenericMethod } | Select-Object -First 1

function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    return $netTask.Result
}

[Windows.Devices.Bluetooth.BluetoothDevice, Windows.Devices.Bluetooth, ContentType=WindowsRuntime] | Out-Null
[Windows.Networking.HostName, Windows.Networking, ContentType=WindowsRuntime] | Out-Null
[Windows.Networking.Sockets.StreamSocket, Windows.Networking.Sockets, ContentType=WindowsRuntime] | Out-Null

$mac = [UInt64]0x541589DCA579
$op = [Windows.Devices.Bluetooth.BluetoothDevice]::FromBluetoothAddressAsync($mac)
$dev = Await $op ([Windows.Devices.Bluetooth.BluetoothDevice])

Write-Output "Initial ConnectionStatus: $($dev.ConnectionStatus)"

# Try opening an RFCOMM stream socket to wake/trigger connection
$rfOp = $dev.GetRfcommServicesAsync()
$rfServices = Await $rfOp ([Windows.Devices.Bluetooth.Rfcomm.RfcommDeviceServicesResult])
if ($rfServices.Services.Count -gt 0) {
    $svc = $rfServices.Services[0]
    Write-Output "Connecting to RFCOMM Service: $($svc.ServiceId.AsString()) (Host: $($svc.ConnectionHostName.DisplayName), SvcName: $($svc.ConnectionServiceName))"
    $socket = New-Object Windows.Networking.Sockets.StreamSocket
    try {
        $connOp = $socket.ConnectAsync($svc.ConnectionHostName, $svc.ConnectionServiceName)
        $netTask = [System.WindowsRuntimeSystemExtensions]::AsTask($connOp)
        $netTask.Wait(5000) | Out-Null
        Write-Output "Socket Connect returned successfully!"
    } catch {
        Write-Output "Socket Connect result: $($_.Exception.Message)"
    }
}

Start-Sleep -Seconds 2

# Check endpoint status in Windows
$pnp = Get-PnpDevice -InstanceId "SWD\MMDEVAPI\{0.0.0.00000000}.{8C260B12-CA22-4DF8-B71F-DD78EBA2CA15}" -ErrorAction SilentlyContinue
Write-Output "PnP Endpoint Present: $($pnp.Present), Status: $($pnp.Status)"
