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

$selector = [Windows.Devices.Bluetooth.BluetoothDevice]::GetDeviceSelectorFromBluetoothAddress(0x541589DCA579)
$devs = Await ([Windows.Devices.Enumeration.DeviceInformation]::FindAllAsync($selector)) ([Windows.Devices.Enumeration.DeviceInformationCollection])

foreach ($d in $devs) {
    Write-Output "Name: $($d.Name)"
    Write-Output "DeviceInformation.Id: $($d.Id)"
    Write-Output "Kind: $($d.Kind)"
    Write-Output "IsPaired: $($d.Pairing.IsPaired)"
}

$devOp = [Windows.Devices.Bluetooth.BluetoothDevice]::FromBluetoothAddressAsync(0x541589DCA579)
$dev = Await $devOp ([Windows.Devices.Bluetooth.BluetoothDevice])
if ($dev) {
    Write-Output "BluetoothDevice.Name: $($dev.Name)"
    Write-Output "BluetoothAddress (Hex): $($dev.BluetoothAddress.ToString('X12'))"
    Write-Output "BluetoothDevice.DeviceId: $($dev.DeviceId)"
    Write-Output "ConnectionStatus: $($dev.ConnectionStatus)"
}
