
using System;
using System.Runtime.InteropServices;

public class BluetoothInterop {
    [DllImport("BluetoothApis.dll", SetLastError = true)]
    public static extern IntPtr BluetoothFindFirstRadio(ref BLUETOOTH_FIND_RADIO_PARAMS pbtfrp, out IntPtr phRadio);

    [DllImport("BluetoothApis.dll", SetLastError = true)]
    public static extern bool BluetoothFindNextRadio(IntPtr hFind, out IntPtr phRadio);

    [DllImport("BluetoothApis.dll", SetLastError = true)]
    public static extern bool BluetoothFindRadioClose(IntPtr hFind);

    [DllImport("BluetoothApis.dll", SetLastError = true)]
    public static extern uint BluetoothGetRadioInfo(IntPtr hRadio, ref BLUETOOTH_RADIO_INFO pRadioInfo);

    [DllImport("BluetoothApis.dll", SetLastError = true)]
    public static extern uint BluetoothSetServiceState(IntPtr hRadio, ref BLUETOOTH_DEVICE_INFO pbtdi, ref Guid pGuidService, uint dwServiceFlags);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern bool CloseHandle(IntPtr handle);

    [StructLayout(LayoutKind.Sequential)]
    public struct BLUETOOTH_FIND_RADIO_PARAMS {
        public uint dwSize;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct BLUETOOTH_RADIO_INFO {
        public uint dwSize;
        public ulong address;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 248)]
        public string szName;
        public uint ulClassofDevice;
        public ushort lmpSubversion;
        public ushort manufacturer;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct BLUETOOTH_DEVICE_INFO {
        public uint dwSize;
        public ulong Address;
        public uint ulClassofDevice;
        [MarshalAs(UnmanagedType.Bool)]
        public bool fConnected;
        [MarshalAs(UnmanagedType.Bool)]
        public bool fRemembered;
        [MarshalAs(UnmanagedType.Bool)]
        public bool fAuthenticated;
        public SYSTEMTIME stLastSeen;
        public SYSTEMTIME stLastUsed;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 248)]
        public string szName;
    }

    public struct SYSTEMTIME {
        public ushort wYear, wMonth, wDayOfWeek, wDay, wHour, wMinute, wSecond, wMilliseconds;
    }
}
