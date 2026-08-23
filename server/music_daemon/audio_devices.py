"""
Audio output device detection and management for Windows WASAPI endpoints.
"""

import logging
import re
import subprocess
from typing import List, Dict, Optional

logger = logging.getLogger("music_daemon.audio_devices")


def list_audio_devices(mpv_binary: str = r"D:\AnimusSmartRoom\server\bin\mpv.com") -> List[Dict[str, str]]:
    """
    Queries mpv for available audio devices on the Windows system.
    Safely handles nested parentheses in device descriptions like 'Speakers (LG SNC4R(79))'.
    """
    devices = []
    try:
        res = subprocess.run(
            [mpv_binary, "--audio-device=help"],
            capture_output=True,
            text=True,
            timeout=5
        )
        # Regex matching: 'device_id' (Device Name Description)
        # e.g. 'wasapi/{8c260b12-ca22-4df8-b71f-dd78eba2ca15}' (Speakers (LG SNC4R(79)))
        pattern = re.compile(r"^'([^']+)'\s+\((.*)\)$")
        for raw_line in res.stdout.splitlines():
            line = raw_line.strip()
            match = pattern.match(line)
            if match:
                dev_id = match.group(1).strip()
                dev_name = match.group(2).strip()
                devices.append({
                    "id": dev_id,
                    "name": dev_name
                })
    except Exception as e:
        logger.error(f"Error enumerating audio devices: {e}")

    if not devices:
        devices.append({"id": "auto", "name": "Autoselect device (Default)"})

    return devices


def find_preferred_audio_device(
    keyword: str = "LG SNC4R",
    mpv_binary: str = r"D:\AnimusSmartRoom\server\bin\mpv.com"
) -> Dict[str, str]:
    """
    Scans detected audio devices for a match on the friendly name or ID.
    Returns a dict with 'id' and 'name'. Falls back to 'auto' if no match is found.
    """
    devices = list_audio_devices(mpv_binary=mpv_binary)
    clean_keyword = keyword.lower().strip()

    # 1. Match on friendly name first (e.g. contains 'lg snc4r')
    for dev in devices:
        if dev["id"] != "auto" and clean_keyword in dev["name"].lower():
            logger.info(f"[AUDIO_DEVICE_DETECTED] Found preferred device by name '{dev['name']}': id='{dev['id']}'")
            return dev

    # 2. Match on device id
    for dev in devices:
        if dev["id"] != "auto" and clean_keyword in dev["id"].lower():
            logger.info(f"[AUDIO_DEVICE_DETECTED] Found preferred device by id '{dev['id']}': name='{dev['name']}'")
            return dev

    logger.info(f"[AUDIO_DEVICE_FALLBACK] Preferred device '{keyword}' not found in active endpoints. Falling back to 'auto'.")
    return {"id": "auto", "name": "Autoselect device (Default)"}
