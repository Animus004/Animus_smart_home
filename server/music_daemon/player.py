"""
Headless mpv player controller using Windows Named Pipe JSON-RPC IPC.
Supports deterministic WASAPI device routing, automatic Bluetooth endpoint reconnection,
playback, pause, resume, volume, and rich telemetry.
"""

import json
import logging
import os
import subprocess
import time
from typing import Optional, Dict, Any, Tuple

from bluetooth_helper import BluetoothAudioHelper

logger = logging.getLogger("music_daemon.player")


class MpvPlayer:
    """
    Manages a single headless mpv background process and controls playback
    via JSON-RPC over a Windows Named Pipe.
    Enforces deterministic routing to the LG soundbar and prevents silent fallback to monitor speakers.
    """
    PIPE_NAME = r"\\.\pipe\mpv-animus"

    def __init__(
        self,
        mpv_path: str = r"D:\AnimusSmartRoom\server\bin\mpv.com",
        preferred_device_keyword: str = "LG SNC4R"
    ):
        self.mpv_path = mpv_path
        self.preferred_device_keyword = preferred_device_keyword
        self.bt_helper = BluetoothAudioHelper(preferred_keyword=preferred_device_keyword, mpv_binary=mpv_path)
        self.process: Optional[subprocess.Popen] = None
        self.current_track: Optional[Dict[str, Any]] = None
        self._playback_status: str = "IDLE"
        self._active_audio_device_id: Optional[str] = None
        self._active_audio_device_name: Optional[str] = None
        self._audio_output_status: str = "DISCONNECTED"

    def _ensure_mpv_running(self, audio_device_id: str):
        if self.process and self.process.poll() is None:
            return

        logger.info(f"[PC_MUSIC_PLAYER] Starting mpv process with IPC pipe={self.PIPE_NAME}, audio-device={audio_device_id} ({self._active_audio_device_name})")
        cmd = [
            self.mpv_path,
            "--idle=yes",
            "--no-video",
            f"--input-ipc-server={self.PIPE_NAME}",
            f"--audio-device={audio_device_id}",
            "--volume=100",
            "--keep-open=yes",
        ]

        try:
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            )
            # Poll for pipe availability up to 3 seconds
            start_wait = time.time()
            connected = False
            while time.time() - start_wait < 3.0:
                try:
                    with open(self.PIPE_NAME, "r+b", buffering=0) as test_pipe:
                        connected = True
                        break
                except Exception:
                    time.sleep(0.1)

            if connected:
                logger.info(f"[PC_MUSIC_PLAYER] mpv started and IPC pipe ready with PID {self.process.pid}")
            else:
                logger.warning(f"[PC_MUSIC_PLAYER] mpv started with PID {self.process.pid} but IPC pipe wait timed out")
        except Exception as e:
            logger.error(f"[PC_MUSIC_PLAYER_ERROR] Failed to start mpv process: {e}", exc_info=True)
            raise

    def _send_ipc_command(self, command: list, timeout: float = 2.0) -> Optional[Dict[str, Any]]:
        if not self.process or self.process.poll() is not None:
            return None
        req = json.dumps({"command": command}) + "\n"

        for attempt in range(3):
            try:
                with open(self.PIPE_NAME, "r+b", buffering=0) as pipe:
                    pipe.write(req.encode("utf-8"))
                    pipe.flush()
                    line = pipe.readline().decode("utf-8").strip()
                    if line:
                        return json.loads(line)
            except Exception as e:
                if attempt == 2:
                    logger.warning(f"[PC_MUSIC_IPC_WARNING] IPC command {command} error: {e}")
                time.sleep(0.15)
        return None

    def play(self, stream_url: str, title: str, artist: str, duration: Optional[int] = None, thumbnail_url: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Ensures LG audio endpoint is available before starting playback.
        Returns (success: bool, error_reason_or_None).
        """
        # 1. Ensure deterministic audio endpoint
        ready, lg_dev, status_code = self.bt_helper.ensure_audio_endpoint()
        if not ready or not lg_dev:
            self._audio_output_status = "DISCONNECTED"
            self._active_audio_device_id = None
            self._active_audio_device_name = None
            self._playback_status = "STOPPED"
            logger.error(f"[PC_MUSIC_PLAY_BLOCKED] Cannot start playback. Reason: AUDIO_OUTPUT_UNAVAILABLE")
            return False, "AUDIO_OUTPUT_UNAVAILABLE"

        self._active_audio_device_id = lg_dev["id"]
        self._active_audio_device_name = lg_dev["name"]
        self._audio_output_status = "CONNECTED"

        # 2. Launch or update mpv instance with exact WASAPI endpoint
        self._ensure_mpv_running(self._active_audio_device_id)
        self._send_ipc_command(["set_property", "audio-device", self._active_audio_device_id])

        logger.info(f"[PC_MUSIC_PLAYING] Loading stream into mpv: '{title}' by '{artist}' (audio-device={self._active_audio_device_id})")

        res = self._send_ipc_command(["loadfile", stream_url, "replace"])
        if res and res.get("error") == "success":
            self.current_track = {
                "title": title,
                "artist": artist,
                "duration": duration,
                "thumbnail_url": thumbnail_url,
                "started_at": time.time()
            }
            self._playback_status = "PLAYING"
            self._send_ipc_command(["set_property", "pause", False])
            return True, None
        else:
            logger.error(f"[PC_MUSIC_PLAY_FAILED] mpv loadfile response: {res}")
            return False, "ENGINE_ERROR"

    def pause(self) -> bool:
        """
        Pauses current playback.
        """
        if not self.process or self.process.poll() is not None:
            return False
        res = self._send_ipc_command(["set_property", "pause", True])
        if res and res.get("error") == "success":
            self._playback_status = "PAUSED"
            logger.info("[PC_MUSIC_PAUSE] Playback paused.")
            return True
        return False

    def resume(self) -> bool:
        """
        Resumes current playback.
        """
        if not self.process or self.process.poll() is not None:
            return False
        res = self._send_ipc_command(["set_property", "pause", False])
        if res and res.get("error") == "success":
            self._playback_status = "PLAYING"
            logger.info("[PC_MUSIC_RESUME] Playback resumed.")
            return True
        return False

    def set_volume(self, volume: int) -> int:
        """
        Sets playback volume (0-100). Returns the applied volume.
        """
        if not self.process or self.process.poll() is not None:
            return 100
        clamped_vol = max(0, min(100, volume))
        res = self._send_ipc_command(["set_property", "volume", clamped_vol])
        if res and res.get("error") == "success":
            logger.info(f"[PC_MUSIC_VOLUME] Volume set to {clamped_vol}%.")
            return clamped_vol
        return 100

    def stop(self) -> bool:
        """
        Stops playback and clears current track.
        """
        if not self.process or self.process.poll() is not None:
            self._playback_status = "STOPPED"
            self.current_track = None
            return True

        self._send_ipc_command(["stop"])
        self._playback_status = "STOPPED"
        self.current_track = None
        logger.info("[PC_MUSIC_STOP] Playback stopped.")
        return True

    def get_status(self) -> Dict[str, Any]:
        """
        Returns the current playback status, track info, volume, audio routing, and Bluetooth status.
        """
        # Re-check live endpoint presence if idle or not playing
        if self._playback_status != "PLAYING":
            lg_dev, _ = self.bt_helper.scan_active_endpoints()
            if lg_dev:
                self._active_audio_device_id = lg_dev["id"]
                self._active_audio_device_name = lg_dev["name"]
                self._audio_output_status = "CONNECTED"
            else:
                self._audio_output_status = "DISCONNECTED"
                self._active_audio_device_id = None
                self._active_audio_device_name = None

        if not self.process or self.process.poll() is not None:
            return {
                "status": "IDLE",
                "title": None,
                "artist": None,
                "duration": None,
                "position": None,
                "volume": 100,
                "audio_output_status": self._audio_output_status,
                "audio_device_id": self._active_audio_device_id,
                "audio_device_name": self._active_audio_device_name
            }

        pause_res = self._send_ipc_command(["get_property", "pause"])
        pos_res = self._send_ipc_command(["get_property", "time-pos"])
        vol_res = self._send_ipc_command(["get_property", "volume"])

        is_paused = pause_res.get("data", False) if pause_res else False
        pos_seconds = pos_res.get("data") if pos_res and isinstance(pos_res.get("data"), (int, float)) else None
        volume = vol_res.get("data", 100) if vol_res else 100

        status = "IDLE"
        if self.current_track:
            status = "PAUSED" if is_paused else "PLAYING"

        return {
            "status": status,
            "title": self.current_track.get("title") if self.current_track else None,
            "artist": self.current_track.get("artist") if self.current_track else None,
            "duration": self.current_track.get("duration") if self.current_track else None,
            "position": int(pos_seconds) if pos_seconds is not None else None,
            "thumbnail_url": self.current_track.get("thumbnail_url") if self.current_track else None,
            "volume": int(volume),
            "audio_output_status": self._audio_output_status,
            "audio_device_id": self._active_audio_device_id,
            "audio_device_name": self._active_audio_device_name
        }

    def shutdown(self):
        """
        Gracefully terminates mpv process.
        """
        if self.process and self.process.poll() is None:
            logger.info("[PC_MUSIC_SHUTDOWN] Terminating mpv process...")
            try:
                self._send_ipc_command(["quit"])
                self.process.wait(timeout=2)
            except Exception:
                self.process.kill()
            self.process = None
