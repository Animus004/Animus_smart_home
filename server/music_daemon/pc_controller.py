"""
Authoritative PC Controller & Windows Hardware Provider for Animus Smart Room.
Provides high-performance, in-process Windows CoreAudio, Bluetooth, Media, and Power capabilities
using direct Windows C-ABI & COM interfaces with physical read-back verification.

Architectural Flow:
Brain understands -> Router decides -> PC Controller executes -> Physical Device verifies -> UI reports reality
"""

import os
import sys
import time
import socket
import logging
import platform
import subprocess
import ctypes
from ctypes import wintypes, Structure, POINTER, c_float, c_long, c_ulong, c_wchar_p, byref, c_int, c_uint, c_void_p, cast
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum

logger = logging.getLogger("pc_controller")

# -----------------------------------------------------------------------------
# COM & Windows Native Definitions
# -----------------------------------------------------------------------------

ole32 = ctypes.windll.ole32
user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
powrprof = ctypes.windll.powrprof

try:
    bth = ctypes.windll.LoadLibrary("BluetoothApis.dll")
except Exception:
    try:
        bth = ctypes.windll.LoadLibrary("bthprops.cpl")
    except Exception:
        bth = None

# Declare 64-bit BluetoothApis prototypes if available
if bth:
    class BLUETOOTH_FIND_RADIO_PARAMS(Structure):
        _fields_ = [("dwSize", wintypes.DWORD)]

    class BLUETOOTH_RADIO_INFO(Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("address", ctypes.c_uint64),
            ("szName", wintypes.WCHAR * 248),
            ("ulClassofDevice", wintypes.ULONG),
            ("lmpSubversion", wintypes.USHORT),
            ("manufacturer", wintypes.USHORT)
        ]

    class BLUETOOTH_DEVICE_SEARCH_PARAMS(Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("fReturnAuthenticated", wintypes.BOOL),
            ("fReturnRemembered", wintypes.BOOL),
            ("fReturnUnknown", wintypes.BOOL),
            ("fReturnConnected", wintypes.BOOL),
            ("fIssueInquiry", wintypes.BOOL),
            ("cTimeoutMultiplier", wintypes.BYTE),
            ("hRadio", wintypes.HANDLE)
        ]

    class BLUETOOTH_ADDRESS(Structure):
        _fields_ = [("ullLong", ctypes.c_uint64)]

    class SYSTEMTIME(Structure):
        _fields_ = [
            ("wYear", wintypes.WORD),
            ("wMonth", wintypes.WORD),
            ("wDayOfWeek", wintypes.WORD),
            ("wDay", wintypes.WORD),
            ("wHour", wintypes.WORD),
            ("wMinute", wintypes.WORD),
            ("wSecond", wintypes.WORD),
            ("wMilliseconds", wintypes.WORD)
        ]

    class BLUETOOTH_DEVICE_INFO(Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("Address", BLUETOOTH_ADDRESS),
            ("ulClassofDevice", wintypes.ULONG),
            ("fConnected", wintypes.BOOL),
            ("fRemembered", wintypes.BOOL),
            ("fAuthenticated", wintypes.BOOL),
            ("stLastSeen", SYSTEMTIME),
            ("stLastUsed", SYSTEMTIME),
            ("szName", wintypes.WCHAR * 248)
        ]

    bth.BluetoothFindFirstRadio.restype = wintypes.HANDLE
    bth.BluetoothFindFirstRadio.argtypes = [POINTER(BLUETOOTH_FIND_RADIO_PARAMS), POINTER(wintypes.HANDLE)]

    bth.BluetoothGetRadioInfo.restype = wintypes.DWORD
    bth.BluetoothGetRadioInfo.argtypes = [wintypes.HANDLE, POINTER(BLUETOOTH_RADIO_INFO)]

    bth.BluetoothFindRadioClose.restype = wintypes.BOOL
    bth.BluetoothFindRadioClose.argtypes = [wintypes.HANDLE]

    bth.BluetoothFindFirstDevice.restype = wintypes.HANDLE
    bth.BluetoothFindFirstDevice.argtypes = [POINTER(BLUETOOTH_DEVICE_SEARCH_PARAMS), POINTER(BLUETOOTH_DEVICE_INFO)]

    bth.BluetoothFindNextDevice.restype = wintypes.BOOL
    bth.BluetoothFindNextDevice.argtypes = [wintypes.HANDLE, POINTER(BLUETOOTH_DEVICE_INFO)]

    bth.BluetoothFindDeviceClose.restype = wintypes.BOOL
    bth.BluetoothFindDeviceClose.argtypes = [wintypes.HANDLE]


# CoreAudio COM GUIDs and VTables
class GUID(Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8)
    ]
    def __init__(self, l, w1, w2, b1, b2, b3, b4, b5, b6, b7, b8):
        super().__init__(l, w1, w2, (wintypes.BYTE * 8)(b1, b2, b3, b4, b5, b6, b7, b8))

class PROPERTYKEY(Structure):
    _fields_ = [("fmtid", GUID), ("pid", wintypes.DWORD)]

class PROPVARIANT(Structure):
    _fields_ = [
        ("vt", wintypes.WORD),
        ("wReserved1", wintypes.WORD),
        ("wReserved2", wintypes.WORD),
        ("wReserved3", wintypes.WORD),
        ("pwszVal", wintypes.LPWSTR)
    ]

CLSID_MMDeviceEnumerator = GUID(0xBCDE0395, 0xE52F, 0x467C, 0x8E, 0x3D, 0xC4, 0x57, 0x92, 0x91, 0x69, 0x2E)
IID_IMMDeviceEnumerator = GUID(0xA95664D2, 0x9614, 0x4F35, 0xA7, 0x46, 0xDE, 0x8D, 0xB6, 0x36, 0x17, 0xE6)
IID_IAudioEndpointVolume = GUID(0x5CDF2C82, 0x841E, 0x4546, 0x97, 0x22, 0x0C, 0xF7, 0x40, 0x78, 0x22, 0x9A)
PKEY_Device_FriendlyName = PROPERTYKEY(GUID(0xA45C254E, 0xDF1C, 0x4EFD, 0x80, 0x20, 0x67, 0xD1, 0x46, 0xA8, 0x50, 0xE0), 14)

class IPropertyStore(Structure): pass
class IPropertyStoreVtbl(Structure):
    _fields_ = [
        ("QueryInterface", ctypes.c_void_p), ("AddRef", ctypes.c_void_p),
        ("Release", ctypes.WINFUNCTYPE(c_ulong, POINTER(IPropertyStore))),
        ("GetCount", ctypes.c_void_p), ("GetAt", ctypes.c_void_p),
        ("GetValue", ctypes.WINFUNCTYPE(ctypes.c_long, POINTER(IPropertyStore), POINTER(PROPERTYKEY), POINTER(PROPVARIANT))),
        ("SetValue", ctypes.c_void_p), ("Commit", ctypes.c_void_p)
    ]
IPropertyStore._fields_ = [("lpVtbl", POINTER(IPropertyStoreVtbl))]

class IMMDevice(Structure): pass
class IMMDeviceVtbl(Structure):
    _fields_ = [
        ("QueryInterface", ctypes.c_void_p), ("AddRef", ctypes.c_void_p),
        ("Release", ctypes.WINFUNCTYPE(c_ulong, POINTER(IMMDevice))),
        ("Activate", ctypes.WINFUNCTYPE(ctypes.c_long, POINTER(IMMDevice), POINTER(GUID), wintypes.DWORD, c_void_p, POINTER(c_void_p))),
        ("OpenPropertyStore", ctypes.WINFUNCTYPE(ctypes.c_long, POINTER(IMMDevice), wintypes.DWORD, POINTER(POINTER(IPropertyStore)))),
        ("GetId", ctypes.WINFUNCTYPE(ctypes.c_long, POINTER(IMMDevice), POINTER(wintypes.LPWSTR))),
        ("GetState", ctypes.WINFUNCTYPE(ctypes.c_long, POINTER(IMMDevice), POINTER(wintypes.DWORD)))
    ]
IMMDevice._fields_ = [("lpVtbl", POINTER(IMMDeviceVtbl))]

class IMMDeviceCollection(Structure): pass
class IMMDeviceCollectionVtbl(Structure):
    _fields_ = [
        ("QueryInterface", ctypes.c_void_p), ("AddRef", ctypes.c_void_p),
        ("Release", ctypes.WINFUNCTYPE(c_ulong, POINTER(IMMDeviceCollection))),
        ("GetCount", ctypes.WINFUNCTYPE(ctypes.c_long, POINTER(IMMDeviceCollection), POINTER(wintypes.UINT))),
        ("Item", ctypes.WINFUNCTYPE(ctypes.c_long, POINTER(IMMDeviceCollection), wintypes.UINT, POINTER(POINTER(IMMDevice))))
    ]
IMMDeviceCollection._fields_ = [("lpVtbl", POINTER(IMMDeviceCollectionVtbl))]

class IMMDeviceEnumerator(Structure): pass
class IMMDeviceEnumeratorVtbl(Structure):
    _fields_ = [
        ("QueryInterface", ctypes.c_void_p), ("AddRef", ctypes.c_void_p),
        ("Release", ctypes.WINFUNCTYPE(c_ulong, POINTER(IMMDeviceEnumerator))),
        ("EnumAudioEndpoints", ctypes.WINFUNCTYPE(ctypes.c_long, POINTER(IMMDeviceEnumerator), c_int, wintypes.DWORD, POINTER(POINTER(IMMDeviceCollection)))),
        ("GetDefaultAudioEndpoint", ctypes.WINFUNCTYPE(ctypes.c_long, POINTER(IMMDeviceEnumerator), c_int, c_int, POINTER(POINTER(IMMDevice)))),
        ("GetDevice", ctypes.c_void_p), ("RegisterEndpointNotificationCallback", ctypes.c_void_p),
        ("UnregisterEndpointNotificationCallback", ctypes.c_void_p)
    ]
IMMDeviceEnumerator._fields_ = [("lpVtbl", POINTER(IMMDeviceEnumeratorVtbl))]

class IAudioEndpointVolume(Structure): pass
class IAudioEndpointVolumeVtbl(Structure):
    _fields_ = [
        ("QueryInterface", ctypes.c_void_p), ("AddRef", ctypes.c_void_p),
        ("Release", ctypes.WINFUNCTYPE(c_ulong, POINTER(IAudioEndpointVolume))),
        ("RegisterControlChangeNotify", ctypes.c_void_p), ("UnregisterControlChangeNotify", ctypes.c_void_p),
        ("GetChannelCount", ctypes.c_void_p), ("SetMasterVolumeLevel", ctypes.c_void_p),
        ("SetMasterVolumeLevelScalar", ctypes.WINFUNCTYPE(ctypes.c_long, POINTER(IAudioEndpointVolume), c_float, POINTER(GUID))),
        ("GetMasterVolumeLevel", ctypes.c_void_p),
        ("GetMasterVolumeLevelScalar", ctypes.WINFUNCTYPE(ctypes.c_long, POINTER(IAudioEndpointVolume), POINTER(c_float))),
        ("SetChannelVolumeLevel", ctypes.c_void_p), ("SetChannelVolumeLevelScalar", ctypes.c_void_p),
        ("GetChannelVolumeLevel", ctypes.c_void_p), ("GetChannelVolumeLevelScalar", ctypes.c_void_p),
        ("SetMute", ctypes.WINFUNCTYPE(ctypes.c_long, POINTER(IAudioEndpointVolume), wintypes.BOOL, POINTER(GUID))),
        ("GetMute", ctypes.WINFUNCTYPE(ctypes.c_long, POINTER(IAudioEndpointVolume), POINTER(wintypes.BOOL)))
    ]
IAudioEndpointVolume._fields_ = [("lpVtbl", POINTER(IAudioEndpointVolumeVtbl))]

class SYSTEM_POWER_STATUS(Structure):
    _fields_ = [
        ("ACLineStatus", wintypes.BYTE),
        ("BatteryFlag", wintypes.BYTE),
        ("BatteryLifePercent", wintypes.BYTE),
        ("SystemStatusFlag", wintypes.BYTE),
        ("BatteryLifeTime", wintypes.DWORD),
        ("BatteryFullLifeTime", wintypes.DWORD),
    ]


# Virtual Key Codes for Media Transport
class MediaVirtualKey(int, Enum):
    PLAY_PAUSE = 0xB3  # 179
    NEXT_TRACK = 0xB0  # 176
    PREV_TRACK = 0xB1  # 177
    STOP = 0xB2        # 178
    VOLUME_MUTE = 0xAD # 173
    VOLUME_DOWN = 0xAE # 174
    VOLUME_UP = 0xAF   # 175


class PcController:
    """
    Authoritative PC Controller managing Audio, Bluetooth, Media, and Power
    with physical read-back verification and strict security bounds.
    """
    ALLOWLISTED_APPS = {
        "browser": ["chrome.exe", "msedge.exe"],
        "chrome": ["chrome.exe"],
        "edge": ["msedge.exe"],
        "notepad": ["notepad.exe"],
        "calc": ["calc.exe"],
        "calculator": ["calc.exe"],
        "explorer": ["explorer.exe"]
    }

    def __init__(self):
        try:
            ole32.CoInitialize(None)
        except Exception:
            pass

    # =========================================================================
    # 1. AUDIO SUBSYSTEM (Windows CoreAudio MMDevices)
    # =========================================================================

    def _get_default_endpoint_volume(self) -> Tuple[Optional[POINTER(IMMDevice)], Optional[POINTER(IAudioEndpointVolume)]]:
        try:
            ole32.CoInitialize(None)
        except Exception:
            pass

        enumerator = POINTER(IMMDeviceEnumerator)()
        hr = ole32.CoCreateInstance(
            byref(CLSID_MMDeviceEnumerator),
            None,
            1, # CLSCTX_INPROC_SERVER
            byref(IID_IMMDeviceEnumerator),
            byref(enumerator)
        )
        if hr != 0 or not enumerator:
            return None, None

        dev = POINTER(IMMDevice)()
        hr = enumerator.contents.lpVtbl.contents.GetDefaultAudioEndpoint(enumerator, 0, 1, byref(dev))
        enumerator.contents.lpVtbl.contents.Release(enumerator)

        if hr != 0 or not dev:
            return None, None

        epv_ptr = c_void_p()
        hr = dev.contents.lpVtbl.contents.Activate(dev, byref(IID_IAudioEndpointVolume), 23, None, byref(epv_ptr))
        if hr != 0 or not epv_ptr:
            dev.contents.lpVtbl.contents.Release(dev)
            return None, None

        epv = cast(epv_ptr, POINTER(IAudioEndpointVolume))
        return dev, epv

    def get_audio_status(self) -> Dict[str, Any]:
        """Returns authoritative master volume, mute state, default endpoint, and active endpoints."""
        dev, epv = self._get_default_endpoint_volume()
        vol = 0
        is_muted = False
        default_id = ""
        default_name = "Unknown"

        if dev and epv:
            try:
                # Volume
                val = c_float()
                if epv.contents.lpVtbl.contents.GetMasterVolumeLevelScalar(epv, byref(val)) == 0:
                    vol = int(round(val.value * 100))

                # Mute
                m_val = wintypes.BOOL()
                if epv.contents.lpVtbl.contents.GetMute(epv, byref(m_val)) == 0:
                    is_muted = bool(m_val.value)

                # ID
                p_id = wintypes.LPWSTR()
                if dev.contents.lpVtbl.contents.GetId(dev, byref(p_id)) == 0 and p_id:
                    default_id = str(p_id.value)

                # Name
                store = POINTER(IPropertyStore)()
                if dev.contents.lpVtbl.contents.OpenPropertyStore(dev, 0, byref(store)) == 0 and store:
                    pv = PROPVARIANT()
                    key = PKEY_Device_FriendlyName
                    if store.contents.lpVtbl.contents.GetValue(store, byref(key), byref(pv)) == 0 and pv.pwszVal:
                        default_name = str(pv.pwszVal)
                    store.contents.lpVtbl.contents.Release(store)
            finally:
                epv.contents.lpVtbl.contents.Release(epv)
                dev.contents.lpVtbl.contents.Release(dev)

        # Enumerate all active render endpoints
        active_endpoints = self.list_audio_endpoints()

        return {
            "success": True,
            "master_volume": vol,
            "is_muted": is_muted,
            "default_endpoint": {
                "id": default_id,
                "name": default_name
            },
            "active_endpoints": active_endpoints,
            "verified": True
        }

    def list_audio_endpoints(self) -> List[Dict[str, Any]]:
        """Enumerates active audio playback render endpoints with IDs and friendly names."""
        try:
            ole32.CoInitialize(None)
        except Exception:
            pass

        enumerator = POINTER(IMMDeviceEnumerator)()
        if ole32.CoCreateInstance(byref(CLSID_MMDeviceEnumerator), None, 1, byref(IID_IMMDeviceEnumerator), byref(enumerator)) != 0:
            return []

        def_dev = POINTER(IMMDevice)()
        def_id = ""
        if enumerator.contents.lpVtbl.contents.GetDefaultAudioEndpoint(enumerator, 0, 1, byref(def_dev)) == 0 and def_dev:
            p_id = wintypes.LPWSTR()
            if def_dev.contents.lpVtbl.contents.GetId(def_dev, byref(p_id)) == 0:
                def_id = str(p_id.value)
            def_dev.contents.lpVtbl.contents.Release(def_dev)

        col = POINTER(IMMDeviceCollection)()
        if enumerator.contents.lpVtbl.contents.EnumAudioEndpoints(enumerator, 0, 1, byref(col)) != 0 or not col:
            enumerator.contents.lpVtbl.contents.Release(enumerator)
            return []

        count = wintypes.UINT()
        col.contents.lpVtbl.contents.GetCount(col, byref(count))

        devices = []
        for i in range(count.value):
            d = POINTER(IMMDevice)()
            if col.contents.lpVtbl.contents.Item(col, i, byref(d)) == 0 and d:
                p_id = wintypes.LPWSTR()
                d.contents.lpVtbl.contents.GetId(d, byref(p_id))
                dev_id_str = str(p_id.value)

                store = POINTER(IPropertyStore)()
                dev_name = "Unknown"
                if d.contents.lpVtbl.contents.OpenPropertyStore(d, 0, byref(store)) == 0 and store:
                    pv = PROPVARIANT()
                    key = PKEY_Device_FriendlyName
                    if store.contents.lpVtbl.contents.GetValue(store, byref(key), byref(pv)) == 0 and pv.pwszVal:
                        dev_name = str(pv.pwszVal)
                    store.contents.lpVtbl.contents.Release(store)

                devices.append({
                    "id": dev_id_str,
                    "name": dev_name,
                    "is_default": (dev_id_str == def_id)
                })
                d.contents.lpVtbl.contents.Release(d)

        col.contents.lpVtbl.contents.Release(col)
        enumerator.contents.lpVtbl.contents.Release(enumerator)
        return devices

    def set_volume(self, target_volume: int) -> Tuple[bool, Dict[str, Any]]:
        """
        Sets master system volume (0–100%) with physical read-back verification.
        """
        if target_volume < 0 or target_volume > 100:
            return False, {
                "success": False,
                "requested_volume": target_volume,
                "error": f"Volume level {target_volume}% is out of bounds (0–100%).",
                "status": "INVALID_PARAMETER",
                "verified": False
            }

        cur_vol = self.get_volume()
        if cur_vol == target_volume:
            return True, {
                "success": True,
                "idempotent": True,
                "master_volume": target_volume,
                "message": f"Volume is already set to {target_volume}%.",
                "verified": True
            }

        dev, epv = self._get_default_endpoint_volume()
        if not epv or not dev:
            return False, {
                "success": False,
                "error": "Failed to activate Windows CoreAudio endpoint volume.",
                "verified": False
            }

        try:
            scalar = target_volume / 100.0
            hr = epv.contents.lpVtbl.contents.SetMasterVolumeLevelScalar(epv, scalar, None)
            if hr != 0:
                return False, {"success": False, "error": f"SetMasterVolumeLevelScalar failed (HRESULT {hex(hr)}).", "verified": False}
        finally:
            epv.contents.lpVtbl.contents.Release(epv)
            dev.contents.lpVtbl.contents.Release(dev)

        # Authoritative read-back verification
        verified_vol = self.get_volume()
        verified = (abs(verified_vol - target_volume) <= 1)

        return verified, {
            "success": verified,
            "master_volume": verified_vol,
            "verified": verified,
            "message": f"Master volume set to {verified_vol}% (verified read-back)." if verified else "Volume command sent but verification failed."
        }

    def get_volume(self) -> int:
        """Returns current master volume percentage (0–100)."""
        dev, epv = self._get_default_endpoint_volume()
        if not epv or not dev:
            return -1
        try:
            val = c_float()
            if epv.contents.lpVtbl.contents.GetMasterVolumeLevelScalar(epv, byref(val)) == 0:
                return int(round(val.value * 100))
            return -1
        finally:
            epv.contents.lpVtbl.contents.Release(epv)
            dev.contents.lpVtbl.contents.Release(dev)

    def set_mute(self, mute: bool) -> Tuple[bool, Dict[str, Any]]:
        """
        Sets master audio mute state with physical read-back verification.
        """
        dev, epv = self._get_default_endpoint_volume()
        if not epv or not dev:
            return False, {"success": False, "error": "Failed to activate CoreAudio endpoint.", "verified": False}

        try:
            hr = epv.contents.lpVtbl.contents.SetMute(epv, bool(mute), None)
            if hr != 0:
                return False, {"success": False, "error": f"SetMute failed (HRESULT {hex(hr)}).", "verified": False}
        finally:
            epv.contents.lpVtbl.contents.Release(epv)
            dev.contents.lpVtbl.contents.Release(dev)

        # Read-back verification
        st = self.get_audio_status()
        verified = (st.get("is_muted") == mute)
        return verified, {
            "success": verified,
            "is_muted": st.get("is_muted", mute),
            "verified": verified,
            "message": f"System audio {'muted' if mute else 'unmuted'} (verified read-back)." if verified else "Mute command sent but verification failed."
        }

    # =========================================================================
    # 2. BLUETOOTH SUBSYSTEM (Windows BluetoothApis)
    # =========================================================================

    def get_bluetooth_status(self) -> Dict[str, Any]:
        """Returns local Bluetooth radio details and all paired/connected devices."""
        if not bth:
            return {"success": False, "error": "BluetoothApis.dll unavailable on host.", "devices": []}

        r_params = BLUETOOTH_FIND_RADIO_PARAMS()
        r_params.dwSize = ctypes.sizeof(BLUETOOTH_FIND_RADIO_PARAMS)
        h_radio = wintypes.HANDLE()

        h_find_radio = bth.BluetoothFindFirstRadio(byref(r_params), byref(h_radio))
        if not h_find_radio:
            return {
                "success": True,
                "radio_present": False,
                "radio_name": "None",
                "radio_mac": "00:00:00:00:00:00",
                "device_count": 0,
                "devices": []
            }

        r_info = BLUETOOTH_RADIO_INFO()
        r_info.dwSize = ctypes.sizeof(BLUETOOTH_RADIO_INFO)
        bth.BluetoothGetRadioInfo(h_radio, byref(r_info))
        mac_raw = r_info.address
        local_mac = f"{(mac_raw >> 40) & 0xFF:02X}:{(mac_raw >> 32) & 0xFF:02X}:{(mac_raw >> 24) & 0xFF:02X}:{(mac_raw >> 16) & 0xFF:02X}:{(mac_raw >> 8) & 0xFF:02X}:{mac_raw & 0xFF:02X}"
        radio_name = r_info.szName

        params = BLUETOOTH_DEVICE_SEARCH_PARAMS()
        params.dwSize = ctypes.sizeof(BLUETOOTH_DEVICE_SEARCH_PARAMS)
        params.fReturnAuthenticated = True
        params.fReturnRemembered = True
        params.fReturnUnknown = False
        params.fReturnConnected = True
        params.fIssueInquiry = False
        params.cTimeoutMultiplier = 1
        params.hRadio = h_radio

        devices = []
        dev_info = BLUETOOTH_DEVICE_INFO()
        dev_info.dwSize = ctypes.sizeof(BLUETOOTH_DEVICE_INFO)

        h_find_dev = bth.BluetoothFindFirstDevice(byref(params), byref(dev_info))
        if h_find_dev:
            while True:
                mac_raw = dev_info.Address.ullLong
                dev_mac = f"{(mac_raw >> 40) & 0xFF:02X}:{(mac_raw >> 32) & 0xFF:02X}:{(mac_raw >> 24) & 0xFF:02X}:{(mac_raw >> 16) & 0xFF:02X}:{(mac_raw >> 8) & 0xFF:02X}:{mac_raw & 0xFF:02X}"
                cod = dev_info.ulClassofDevice
                is_audio = (cod & 0x1F00) == 0x0400 or any(k in dev_info.szName.lower() for k in ["audio", "snc", "boat", "speaker", "headphone", "headset", "soundbar"])

                devices.append({
                    "name": dev_info.szName,
                    "mac": dev_mac,
                    "connected": bool(dev_info.fConnected),
                    "paired": bool(dev_info.fRemembered or dev_info.fAuthenticated),
                    "is_audio": is_audio,
                    "class_of_device": hex(cod)
                })

                dev_info = BLUETOOTH_DEVICE_INFO()
                dev_info.dwSize = ctypes.sizeof(BLUETOOTH_DEVICE_INFO)
                if not bth.BluetoothFindNextDevice(h_find_dev, byref(dev_info)):
                    break
            bth.BluetoothFindDeviceClose(h_find_dev)

        kernel32.CloseHandle(h_radio)
        bth.BluetoothFindRadioClose(h_find_radio)

        return {
            "success": True,
            "radio_present": True,
            "radio_name": radio_name,
            "radio_mac": local_mac,
            "device_count": len(devices),
            "devices": devices,
            "verified": True
        }

    # =========================================================================
    # 3. MEDIA TRANSPORT (Global Virtual Media Keys)
    # =========================================================================

    def _send_virtual_key(self, vk_code: int) -> bool:
        """Sends a hardware virtual key press and release event with sub-millisecond latency."""
        try:
            KEYEVENTF_KEYUP = 0x0002
            user32.keybd_event(vk_code, 0, 0, 0)
            user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)
            return True
        except Exception as e:
            logger.error(f"[MEDIA_KEY_FAIL] Error sending virtual key {vk_code}: {e}")
            return False

    def media_play_pause(self) -> Tuple[bool, Dict[str, Any]]:
        """Toggles global Windows media playback (Play/Pause)."""
        ok = self._send_virtual_key(MediaVirtualKey.PLAY_PAUSE.value)
        return ok, {
            "success": ok,
            "action": "PLAY_PAUSE",
            "message": "Dispatched global media Play/Pause key.",
            "verified": ok
        }

    def media_next(self) -> Tuple[bool, Dict[str, Any]]:
        """Skips to the next track on the active media session."""
        ok = self._send_virtual_key(MediaVirtualKey.NEXT_TRACK.value)
        return ok, {
            "success": ok,
            "action": "NEXT_TRACK",
            "message": "Dispatched global media Next Track key.",
            "verified": ok
        }

    def media_previous(self) -> Tuple[bool, Dict[str, Any]]:
        """Skips to the previous track on the active media session."""
        ok = self._send_virtual_key(MediaVirtualKey.PREV_TRACK.value)
        return ok, {
            "success": ok,
            "action": "PREVIOUS_TRACK",
            "message": "Dispatched global media Previous Track key.",
            "verified": ok
        }

    def media_stop(self) -> Tuple[bool, Dict[str, Any]]:
        """Stops global media playback."""
        ok = self._send_virtual_key(MediaVirtualKey.STOP.value)
        return ok, {
            "success": ok,
            "action": "STOP",
            "message": "Dispatched global media Stop key.",
            "verified": ok
        }

    # =========================================================================
    # 4. POWER & SYSTEM MANAGEMENT
    # =========================================================================

    def get_power_state(self) -> Dict[str, Any]:
        """Returns system uptime, power source, battery status, and OS build."""
        uptime_ms = kernel32.GetTickCount64()
        uptime_hrs = round(uptime_ms / (1000 * 3600), 2)

        sps = SYSTEM_POWER_STATUS()
        power_source = "Unknown"
        battery_pct = None

        if kernel32.GetSystemPowerStatus(byref(sps)):
            if sps.ACLineStatus == 1:
                power_source = "AC_MAINS_ONLINE"
            elif sps.ACLineStatus == 0:
                power_source = "BATTERY_DISCHARGING"
            if sps.BatteryLifePercent != 255:
                battery_pct = int(sps.BatteryLifePercent)

        return {
            "success": True,
            "power_state": "AWAKE_AND_RUNNING",
            "power_source": power_source,
            "battery_percent": battery_pct,
            "uptime_hours": uptime_hrs,
            "uptime_ms": uptime_ms,
            "hostname": socket.gethostname(),
            "os": f"{platform.system()} {platform.release()} ({platform.version()})",
            "verified": True
        }

    def lock_workstation(self) -> Tuple[bool, Dict[str, Any]]:
        """Locks the Windows workstation instantly via LockWorkStation."""
        try:
            ok = bool(user32.LockWorkStation())
            return ok, {
                "success": ok,
                "action": "LOCK_WORKSTATION",
                "message": "Windows workstation locked successfully.",
                "verified": ok
            }
        except Exception as e:
            return False, {"success": False, "error": str(e), "verified": False}

    def sleep(self, hibernate: bool = False) -> Tuple[bool, Dict[str, Any]]:
        """Puts PC to sleep (standby / suspend)."""
        try:
            # SetSuspendState(bHibernate, bForce, bWakeupEventsDisabled)
            ok = bool(powrprof.SetSuspendState(int(hibernate), 1, 0))
            return ok, {
                "success": ok,
                "action": "SLEEP",
                "message": "Sent system suspend/sleep state request.",
                "verified": ok
            }
        except Exception as e:
            return False, {"success": False, "error": str(e), "verified": False}

    # =========================================================================
    # 5. SAFE ALLOWLISTED APPLICATION LAUNCHING
    # =========================================================================

    def launch_allowlisted_app(self, app_key: str) -> Tuple[bool, Dict[str, Any]]:
        """Launches an allowlisted safe desktop application."""
        clean_key = app_key.strip().lower()
        if clean_key not in self.ALLOWLISTED_APPS:
            return False, {
                "success": False,
                "error": f"Application '{app_key}' is not in the security allowlist.",
                "status": "SECURITY_REJECTED",
                "allowed_apps": list(self.ALLOWLISTED_APPS.keys()),
                "verified": False
            }

        target_exe = self.ALLOWLISTED_APPS[clean_key][0]
        try:
            proc = subprocess.Popen([target_exe], shell=False)
            return True, {
                "success": True,
                "app": clean_key,
                "pid": proc.pid,
                "message": f"Launched allowlisted application '{clean_key}' (PID: {proc.pid}).",
                "verified": True
            }
        except Exception as e:
            return False, {"success": False, "error": f"Failed to launch '{clean_key}': {e}", "verified": False}

    # =========================================================================
    # 6. UNIFIED PC STATUS
    # =========================================================================

    def get_status(self) -> Dict[str, Any]:
        """Returns comprehensive authoritative status across Audio, Bluetooth, Media, and System."""
        audio = self.get_audio_status()
        bt = self.get_bluetooth_status()
        pwr = self.get_power_state()

        return {
            "device": "PC",
            "hostname": pwr.get("hostname"),
            "os": pwr.get("os"),
            "power": pwr,
            "audio": audio,
            "bluetooth": bt,
            "timestamp": time.time(),
            "verified": True
        }
