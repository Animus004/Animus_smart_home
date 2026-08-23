
# Inspect DeviceInformation.Pairing and StreamSocket methods
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTaskGeneric = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.IsGenericMethod } | Select-Object -First 1

function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    return $netTask.Result
}

[Windows.Devices.Bluetooth.BluetoothDevice, Windows.Devices.Bluetooth, ContentType=WindowsRuntime] | Out-Null
[Windows.Devices.Enumeration.DeviceInformation, Windows.Devices.Enumeration, ContentType=WindowsRuntime] | Out-Null

$devInfoOp = [Windows.Devices.Enumeration.DeviceInformation]::FindAllAsync([Windows.Devices.Bluetooth.BluetoothDevice]::GetDeviceSelectorFromBluetoothAddress(0x541589DCA579))
$devs = Await $devInfoOp ([Windows.Devices.Enumeration.DeviceInformationCollection])

Write-Output "Found $($devs.Count) devices matching selector"
foreach ($d in $devs) {
    Write-Output "ID: $($d.Id)"
    Write-Output "Name: $($d.Name)"
    Write-Output "Pairing IsPaired: $($d.Pairing.IsPaired)"
    Write-Output "Pairing CanPair: $($d.Pairing.CanPair)"
    Write-Output "Kind: $($d.Kind)"
}

$socketMethods = [Windows.Networking.Sockets.StreamSocket].GetMethods() | Where-Object { $_.Name -eq 'ConnectAsync' }
foreach ($m in $socketMethods) {
    $params = ($m.GetParameters() | ForEach-Object { "$($_.ParameterType.Name) $($_.Name)" }) -join ", "
    Write-Output "ConnectAsync($params)"
}
