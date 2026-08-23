
$source = Get-Content -Path "D:\AnimusSmartRoom\server\music_daemon\BluetoothInterop.cs" -Raw
Add-Type -TypeDefinition $source

$frp = New-Object BluetoothInterop+BLUETOOTH_FIND_RADIO_PARAMS
$frp.dwSize = [System.Runtime.InteropServices.Marshal]::SizeOf([Type][BluetoothInterop+BLUETOOTH_FIND_RADIO_PARAMS])
$hRadio = [IntPtr]::Zero
$hFind = [BluetoothInterop]::BluetoothFindFirstRadio([ref]$frp, [ref]$hRadio)

if ($hFind -ne [IntPtr]::Zero) {
    $rInfo = New-Object BluetoothInterop+BLUETOOTH_RADIO_INFO
    $rInfo.dwSize = [System.Runtime.InteropServices.Marshal]::SizeOf([Type][BluetoothInterop+BLUETOOTH_RADIO_INFO])
    $res = [BluetoothInterop]::BluetoothGetRadioInfo($hRadio, [ref]$rInfo)
    Write-Output "Radio: $($rInfo.szName), Addr: $($rInfo.address.ToString('X'))"

    $a2dpGuid = [Guid]"0000110b-0000-1000-8000-00805f9b34fb"
    $devInfo = New-Object BluetoothInterop+BLUETOOTH_DEVICE_INFO
    $devInfo.dwSize = [System.Runtime.InteropServices.Marshal]::SizeOf([Type][BluetoothInterop+BLUETOOTH_DEVICE_INFO])
    $devInfo.Address = [UInt64]0x541589DCA579

    Write-Output "Calling BluetoothSetServiceState for Audio Sink..."
    # 0 = BLUETOOTH_SERVICE_DISABLE, 1 = BLUETOOTH_SERVICE_ENABLE
    $ret = [BluetoothInterop]::BluetoothSetServiceState($hRadio, [ref]$devInfo, [ref]$a2dpGuid, 1)
    Write-Output "BluetoothSetServiceState result: $ret (0 = ERROR_SUCCESS)"

    [BluetoothInterop]::CloseHandle($hRadio) | Out-Null
    [BluetoothInterop]::BluetoothFindRadioClose($hFind) | Out-Null
} else {
    Write-Output "No Bluetooth radio found via BluetoothFindFirstRadio"
}

Start-Sleep -Seconds 2
$pnp = Get-PnpDevice -InstanceId "SWD\MMDEVAPI\{0.0.0.00000000}.{8C260B12-CA22-4DF8-B71F-DD78EBA2CA15}" -ErrorAction SilentlyContinue
Write-Output "Audio Endpoint Present: $($pnp.Present)"
