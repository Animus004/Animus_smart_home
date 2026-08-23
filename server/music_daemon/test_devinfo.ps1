
# Connect to Bluetooth Audio Device via Windows.Media.Audio or Windows Bluetooth Audio Device Management
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

$mac = [UInt64]0x541589DCA579
$op = [Windows.Devices.Bluetooth.BluetoothDevice]::FromBluetoothAddressAsync($mac)
$dev = Await $op ([Windows.Devices.Bluetooth.BluetoothDevice])

Write-Output "Bluetooth Device Name: $($dev.Name), Status: $($dev.ConnectionStatus)"

# Query all DeviceInformation paired endpoints related to this device
$selector = [Windows.Devices.Bluetooth.BluetoothDevice]::GetDeviceSelectorFromBluetoothAddress($mac)
$devListOp = [Windows.Devices.Enumeration.DeviceInformation]::FindAllAsync($selector)
$devList = Await $devListOp ([Windows.Devices.Enumeration.DeviceInformationCollection])

Write-Output "Matching DevInfo Count: $($devList.Count)"
foreach ($d in $devList) {
    Write-Output "Device: $($d.Name), Id: $($d.Id), IsEnabled: $($d.IsEnabled)"
    if ($d.Pairing) {
        Write-Output "Pairing Custom: $($d.Pairing.Custom -ne $null)"
    }
}
