
# Test DeviceAccessInformation and BluetoothDevice connect via RFCOMM Service
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

Write-Output "WinRT Device Name: $($dev.Name), ConnectionStatus: $($dev.ConnectionStatus)"

$rfOp = $dev.GetRfcommServicesAsync()
$rfServices = Await $rfOp ([Windows.Devices.Bluetooth.Rfcomm.RfcommDeviceServicesResult])
Write-Output "Found $($rfServices.Services.Count) RFCOMM services"

if ($rfServices.Services.Count -gt 0) {
    $svc = $rfServices.Services[0]
    $socket = New-Object Windows.Networking.Sockets.StreamSocket
    $hostName = $svc.ConnectionHostName
    $svcName = $svc.ConnectionServiceName
    Write-Output "Connecting to host: $($hostName.DisplayName) with service: $svcName"
    try {
        $connOp = $socket.ConnectAsync($hostName, $svcName)
        $netTask = [System.WindowsRuntimeSystemExtensions]::AsTask($connOp)
        $netTask.Wait(4000) | Out-Null
        Write-Output "ConnectAsync task completed! IsFaulted: $($netTask.IsFaulted)"
    } catch {
        Write-Output "ConnectAsync Exception: $($_.Exception.Message)"
    }
}

Start-Sleep -Seconds 1
Write-Output "Updated WinRT ConnectionStatus: $($dev.ConnectionStatus)"
$pnp = Get-PnpDevice -InstanceId "SWD\MMDEVAPI\{0.0.0.00000000}.{8C260B12-CA22-4DF8-B71F-DD78EBA2CA15}" -ErrorAction SilentlyContinue
Write-Output "Audio Endpoint Present: $($pnp.Present)"
