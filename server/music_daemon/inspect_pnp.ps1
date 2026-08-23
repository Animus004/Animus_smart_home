
# Inspect BTHENUM devices and test DeviceManagement
Get-PnpDevice | Where-Object { $_.InstanceId -like "*541589DCA579*" } | Select-Object Status, Class, FriendlyName, InstanceId | Format-Table -AutoSize
