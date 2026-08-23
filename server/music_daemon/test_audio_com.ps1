
# Test Windows Audio Endpoint State via CoreAudio MMDeviceAPI COM interface
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public class AudioInterop {
    [ComImport]
    [Guid("BCDE0395-E52F-467C-8E3D-C4579291433E")]
    public class MMDeviceEnumeratorComObject { }

    [Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IMMDeviceEnumerator {
        int EnumAudioEndpoints(int dataFlow, int dwStateMask, out IntPtr ppDevices);
        int GetDefaultAudioEndpoint(int dataFlow, int role, out IntPtr ppEndpoint);
        int GetDevice([MarshalAs(UnmanagedType.LPWStr)] string pwstrId, out IntPtr ppDevice);
        int RegisterEndpointNotificationCallback(IntPtr pClient);
        int UnregisterEndpointNotificationCallback(IntPtr pClient);
    }
}
'@

$enum = New-Object AudioInterop+MMDeviceEnumeratorComObject
$imm = [AudioInterop+IMMDeviceEnumerator]$enum

# 0x00000001 = DEVICE_STATE_ACTIVE
# 0x00000002 = DEVICE_STATE_DISABLED
# 0x00000004 = DEVICE_STATE_NOTPRESENT
# 0x00000008 = DEVICE_STATE_UNPLUGGED
# 0x0000000F = DEVICE_STATEMASK_ALL

Write-Output "CoreAudio MMDeviceEnumerator COM object initialized successfully."
