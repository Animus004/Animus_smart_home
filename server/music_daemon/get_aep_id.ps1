
# Test Windows Device Portal API configuration and AEP selector
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.IsGenericMethod } | Select-Object -First 1
function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    return $netTask.Result
}

[Windows.Devices.Enumeration.DeviceInformation, Windows.Devices.Enumeration, ContentType=WindowsRuntime] | Out-Null
[Windows.Devices.Bluetooth.BluetoothDevice, Windows.Devices.Bluetooth, ContentType=WindowsRuntime] | Out-Null

$mac = [UInt64]0x541589DCA579
$selector = [Windows.Devices.Bluetooth.BluetoothDevice]::GetDeviceSelectorFromBluetoothAddress($mac)
$devs = Await ([Windows.Devices.Enumeration.DeviceInformation]::FindAllAsync($selector)) ([Windows.Devices.Enumeration.DeviceInformationCollection])

Write-Output "=== AEP Association Endpoint for LG SNC4R ==="
foreach ($d in $devs) {
    Write-Output "Name: $($d.Name)"
    Write-Output "Id: $($d.Id)"
    Write-Output "Kind: $($d.Kind)"
    Write-Output "Pairing IsPaired: $($d.Pairing.IsPaired)"
}
