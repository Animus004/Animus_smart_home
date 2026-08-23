Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.IsGenericMethod } | Select-Object -First 1
function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    return $netTask.Result
}
[Windows.Devices.Bluetooth.BluetoothDevice, Windows.Devices.Bluetooth, ContentType=WindowsRuntime] | Out-Null
$dev = Await ([Windows.Devices.Bluetooth.BluetoothDevice]::FromBluetoothAddressAsync(0x541589DCA579)) ([Windows.Devices.Bluetooth.BluetoothDevice])
Write-Output "LG WinRT Name: $($dev.Name), ConnectionStatus: $($dev.ConnectionStatus)"
