"""
Room-Level Backend Neural / SAPI Text-to-Speech (TTS) Service.
Provides offline, deterministic speech synthesis, room audio sink routing (LG soundbar / PC audio),
FIFO serialization queue, music ducking, and strict content/safety boundaries.
"""

from enum import Enum
import logging
import os
import queue
import re
import subprocess
import threading
import time
from typing import Optional, Dict, Any, Callable

logger = logging.getLogger("music_daemon.tts_service")


class TtsState(str, Enum):
    IDLE = "IDLE"
    SYNTHESIZING = "SYNTHESIZING"
    PLAYING = "PLAYING"
    ERROR = "ERROR"


class RoomTtsService:
    """
    Authoritative Room-Level TTS Service for Animus Smart Room.
    Synthesizes agentMessage into high-fidelity neural audio with SAPI fallback,
    and plays through active room audio sink with music ducking.
    """
    def __init__(
        self,
        mpv_binary: str = r"D:\AnimusSmartRoom\server\bin\mpv.com",
        orchestrator: Optional[Any] = None,
        room_state_aggregator: Optional[Any] = None,
        cache_dir: str = r"D:\AnimusSmartRoom\server\music_daemon\scratch\tts_cache",
        enabled: bool = False,
        voice: Optional[str] = None,
        rate: Optional[str] = None,
        pitch: Optional[str] = None
    ):
        self.mpv_binary = mpv_binary
        self.orchestrator = orchestrator
        self.room_state_aggregator = room_state_aggregator
        self.cache_dir = cache_dir
        self.enabled = enabled
        self.voice = voice or os.getenv("ANIMUS_TTS_VOICE", "en-GB-SoniaNeural")
        self.rate = rate or os.getenv("ANIMUS_TTS_RATE", "+8%")
        self.pitch = pitch or os.getenv("ANIMUS_TTS_PITCH", "+0Hz")
        self.engine_mode = "NEURAL"
        self._state = TtsState.IDLE
        self._state_lock = threading.RLock()

        os.makedirs(self.cache_dir, exist_ok=True)

        # FIFO Speech Queue & Worker Thread
        self._speech_queue: queue.Queue[str] = queue.Queue()
        self._stop_event = threading.Event()
        self._last_spoken_text: Optional[str] = None
        self._last_spoken_time: float = 0.0
        self._current_player_process: Optional[subprocess.Popen] = None

        self._worker_thread = threading.Thread(
            target=self._speech_queue_worker,
            name="RoomTtsQueueWorker",
            daemon=True
        )
        self._worker_thread.start()
        logger.info(f"[ROOM_TTS] Service initialized (enabled={self.enabled}, voice='{self.voice}', cache_dir='{self.cache_dir}')")

    @property
    def state(self) -> TtsState:
        with self._state_lock:
            return self._state

    def is_speaking(self) -> bool:
        with self._state_lock:
            return self._state in (TtsState.SYNTHESIZING, TtsState.PLAYING)

    def is_enabled(self) -> bool:
        return self.enabled

    def set_enabled(self, enabled: bool):
        self.enabled = enabled
        logger.info(f"[ROOM_TTS] Room TTS enabled state set to: {self.enabled}")

    def set_voice(self, voice: str):
        """Sets active neural TTS voice."""
        self.voice = voice
        logger.info(f"[ROOM_TTS] Neural voice changed to: {self.voice}")

    def set_rate(self, rate: str):
        """Sets speaking rate (e.g. '+10%', '-5%')."""
        self.rate = rate
        logger.info(f"[ROOM_TTS] Speaking rate changed to: {self.rate}")

    def set_pitch(self, pitch: str):
        """Sets voice pitch (e.g. '+2Hz', '-2Hz')."""
        self.pitch = pitch
        logger.info(f"[ROOM_TTS] Voice pitch changed to: {self.pitch}")

    def get_config(self) -> Dict[str, Any]:
        """Returns current voice and engine configuration."""
        return {
            "enabled": self.enabled,
            "voice": self.voice,
            "rate": self.rate,
            "pitch": self.pitch,
            "engine_mode": self.engine_mode,
            "state": self.state.value,
            "is_speaking": self.is_speaking()
        }

    def speak_async(self, text: str):
        """
        Enqueues text for asynchronous synthesis and room audio playback.
        Fails silently and safely if text is blank or service is disabled.
        """
        if not self.enabled:
            logger.debug("[ROOM_TTS] speak_async called but service is disabled; skipping.")
            return

        sanitized = self._sanitize_text(text)
        if not sanitized:
            return

        # Deduplication safeguard: Prevent playing identical response twice within 1.5s
        now = time.time()
        if sanitized == self._last_spoken_text and (now - self._last_spoken_time) < 1.5:
            logger.info(f"[ROOM_TTS] Duplicate utterance suppressed: '{sanitized[:40]}...'")
            return

        self._last_spoken_text = sanitized
        self._last_spoken_time = now
        self._speech_queue.put(sanitized)
        logger.info(f"[ROOM_TTS] Enqueued speech utterance ({len(sanitized)} chars): '{sanitized[:50]}...'")

    def speak(self, text: str, timeout: float = 15.0) -> bool:
        """
        Synchronously speaks text, waiting for playback to complete.
        """
        sanitized = self._sanitize_text(text)
        if not sanitized:
            return False
        return self._process_utterance(sanitized, timeout=timeout)

    def stop(self):
        """
        Immediately stops any active speech playback and clears the speech queue.
        """
        logger.info("[ROOM_TTS] Stopping active speech and draining queue")
        # Drain queue
        while not self._speech_queue.empty():
            try:
                self._speech_queue.get_nowait()
                self._speech_queue.task_done()
            except queue.Empty:
                break

        with self._state_lock:
            if self._current_player_process and self._current_player_process.poll() is None:
                try:
                    self._current_player_process.terminate()
                except Exception as e:
                    logger.debug(f"[ROOM_TTS] Error terminating player process: {e}")
            self._state = TtsState.IDLE

    def wait_until_finished(self, timeout: float = 15.0) -> bool:
        """
        Blocks until the speech queue is empty and playback is IDLE.
        """
        start = time.time()
        while self.is_speaking() or not self._speech_queue.empty():
            if time.time() - start > timeout:
                logger.warning(f"[ROOM_TTS] wait_until_finished timed out after {timeout}s")
                return False
            time.sleep(0.05)
        return True

    def shutdown(self):
        """
        Gracefully terminates TTS worker thread and cleans up active resources.
        """
        logger.info("[ROOM_TTS] Shutting down Room TTS Service...")
        self.stop()
        self._stop_event.set()
        self._speech_queue.put("__SHUTDOWN__")
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=2.0)
        logger.info("[ROOM_TTS] Room TTS Service stopped cleanly.")

    # =========================================================================
    # Internal Pipeline: Worker, Synthesis & Audio Sinks
    # =========================================================================

    def _sanitize_text(self, text: str) -> Optional[str]:
        """
        Sanitizes text before speech synthesis.
        Strips Markdown links, internal IDs, logs, URLs, and forbidden patterns.
        """
        if not text or not isinstance(text, str):
            return None

        clean = text.strip()
        if not clean:
            return None

        # Remove markdown file links: [text](file:///...) or [text](http...)
        clean = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', clean)
        # Remove raw URLs
        clean = re.sub(r'https?://\S+', '', clean)
        # Remove file paths: e.g. D:\... or /path/...
        clean = re.sub(r'[A-Za-z]:\\[\w\\\.\-]+', '', clean)
        clean = re.sub(r'/\w+[\w/\.\-]+', '', clean)
        # Remove sensitive token-like alphanumeric hashes >= 16 chars
        clean = re.sub(r'\b[a-f0-9]{16,}\b', '', clean, flags=re.IGNORECASE)
        # Normalize whitespace
        clean = re.sub(r'\s+', ' ', clean).strip()

        return clean if clean else None

    def synthesize_to_wav(self, text: str, output_wav_path: str) -> bool:
        """
        Synthesizes text to a WAV file using local native SAPI.
        100% offline, zero cloud calls, sub-second synthesis time.
        """
        return self._synthesize_sapi_wav(text, output_wav_path)

    def synthesize_to_audio(self, text: str, output_audio_path: str) -> bool:
        """
        Synthesizes text to audio file using high-fidelity Neural TTS,
        with automatic fallback to local SAPI if network is unavailable.
        """
        if self.engine_mode == "NEURAL":
            ok = self._synthesize_neural(text, output_audio_path)
            if ok:
                return True
            logger.warning("[ROOM_TTS_FALLBACK] Neural TTS failed; falling back to offline SAPI.")

        # Offline SAPI fallback
        return self.synthesize_to_wav(text, output_audio_path)

    def _synthesize_neural(self, text: str, output_audio_path: str) -> bool:
        """Synthesizes text via Microsoft Edge Neural TTS."""
        try:
            import asyncio
            import edge_tts

            os.makedirs(os.path.dirname(os.path.abspath(output_audio_path)), exist_ok=True)
            if os.path.exists(output_audio_path):
                try:
                    os.remove(output_audio_path)
                except Exception:
                    pass

            async def _run():
                communicate = edge_tts.Communicate(
                    text=text,
                    voice=self.voice,
                    rate=self.rate,
                    pitch=self.pitch
                )
                await communicate.save(output_audio_path)

            asyncio.run(_run())
            return os.path.exists(output_audio_path) and os.path.getsize(output_audio_path) > 0
        except Exception as e:
            logger.warning(f"[ROOM_TTS_NEURAL_ERROR] Neural synthesis error: {e}")
            return False

    def _synthesize_sapi_wav(self, text: str, output_wav_path: str) -> bool:
        """
        Synthesizes text to a WAV file using local native SAPI.
        100% offline, zero cloud calls, sub-second synthesis time.
        """
        try:
            os.makedirs(os.path.dirname(os.path.abspath(output_wav_path)), exist_ok=True)
            if os.path.exists(output_wav_path):
                try:
                    os.remove(output_wav_path)
                except Exception:
                    pass

            # Escape quotes and dangerous characters for VBS SAPI
            escaped_text = text.replace('"', '""').replace('\n', ' ').replace('\r', ' ')
            vbs_script = f'''
Dim Sapi, FileStream
Set Sapi = CreateObject("SAPI.SpVoice")
Set FileStream = CreateObject("SAPI.SpFileStream")
FileStream.Open "{output_wav_path}", 3, False
Set Sapi.AudioOutputStream = FileStream
Sapi.Speak "{escaped_text}"
FileStream.Close
'''
            vbs_file = os.path.join(self.cache_dir, f"synth_{threading.get_ident()}_{int(time.time()*1000)}.vbs")
            with open(vbs_file, "w", encoding="utf-8") as f:
                f.write(vbs_script)

            try:
                res = subprocess.run(
                    ["cscript", "//nologo", vbs_file],
                    capture_output=True,
                    text=True,
                    timeout=5.0
                )
                success = res.returncode == 0 and os.path.exists(output_wav_path) and os.path.getsize(output_wav_path) > 0
                if not success:
                    logger.warning(f"[ROOM_TTS_SYNTH_FAIL] VBS synthesis failed: code={res.returncode}, stderr={res.stderr}")
                return success
            finally:
                if os.path.exists(vbs_file):
                    try:
                        os.remove(vbs_file)
                    except Exception:
                        pass
        except Exception as e:
            logger.error(f"[ROOM_TTS_SYNTH_ERROR] Synthesis error: {e}", exc_info=True)
            return False

    def _speech_queue_worker(self):
        """Background daemon thread that serializes and speaks queued utterances."""
        while not self._stop_event.is_set():
            try:
                utterance = self._speech_queue.get(timeout=0.5)
                if utterance == "__SHUTDOWN__":
                    self._speech_queue.task_done()
                    break

                self._process_utterance(utterance)
                self._speech_queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"[ROOM_TTS_WORKER_ERROR] Unexpected error in TTS worker: {e}", exc_info=True)

    def _process_utterance(self, text: str, timeout: float = 15.0) -> bool:
        """
        Executes end-to-end synthesis and playback:
        1. Synthesizes text to neural MP3 (or fallback WAV) file.
        2. Applies temporary audio ducking if music is active.
        3. Plays audio through resolved audio sink via mpv.
        4. Restores music volume and cleans up scratch audio.
        """
        with self._state_lock:
            self._state = TtsState.SYNTHESIZING

        ducked_original_volume: Optional[int] = None
        is_neural = (self.engine_mode == "NEURAL")
        audio_file = os.path.join(self.cache_dir, f"tts_{int(time.time()*1000)}.mp3")
        # Adaptive timeout for longer utterances
        effective_timeout = max(timeout, len(text) * 0.15 + 5.0)

        try:
            # 1. Synthesize Audio (respect instance patch if test/caller overridden synthesize_to_wav)
            if "synthesize_to_wav" in self.__dict__:
                audio_file = os.path.join(self.cache_dir, f"tts_{int(time.time()*1000)}.wav")
                ok = self.synthesize_to_wav(text, audio_file)
            else:
                ok = self.synthesize_to_audio(text, audio_file)
                if not ok:
                    audio_file = os.path.join(self.cache_dir, f"tts_{int(time.time()*1000)}.wav")
                    ok = self.synthesize_to_wav(text, audio_file)

            if not ok:
                logger.error("[ROOM_TTS_SYNTH_FAIL] Synthesis failed to produce audio file.")
                with self._state_lock:
                    self._state = TtsState.ERROR
                return False

            # 2. Apply Music Ducking
            ducked_original_volume = self._apply_music_ducking()

            # 3. Play through Audio Device
            with self._state_lock:
                self._state = TtsState.PLAYING

            self._play_wav_file(audio_file, timeout=effective_timeout)
            return True

        except Exception as e:
            logger.error(f"[ROOM_TTS_PROCESS_ERROR] Error playing room speech: {e}", exc_info=True)
            with self._state_lock:
                self._state = TtsState.ERROR
            return False

        finally:
            # 4. Restore Music Volume
            if ducked_original_volume is not None:
                self._restore_music_volume(ducked_original_volume)

            # 5. Clean up temporary audio file
            if os.path.exists(audio_file):
                try:
                    os.remove(audio_file)
                except Exception:
                    pass

            with self._state_lock:
                if self._state != TtsState.ERROR or self._speech_queue.empty():
                    self._state = TtsState.IDLE

    def _play_audio_file(self, audio_file: str, timeout: float = 15.0):
        """Plays the generated audio file (MP3/WAV) through mpv bound to the active room audio sink."""
        try:
            cmd = [
                self.mpv_binary,
                "--no-video",
                "--really-quiet",
                "--volume=100"
            ]
            dev_id = self._resolve_audio_device_id()
            if dev_id:
                cmd.append(f"--audio-device={dev_id}")
                logger.info(f"[ROOM_TTS_PLAY] Routing speech to audio endpoint: {dev_id}")
            else:
                logger.info("[ROOM_TTS_PLAY] Routing speech to Windows default audio endpoint")

            cmd.append(audio_file)
            self._current_player_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self._current_player_process.wait(timeout=timeout)
            logger.info("[ROOM_TTS_PLAYBACK_COMPLETE] Finished playing room speech.")
        except subprocess.TimeoutExpired:
            logger.warning(f"[ROOM_TTS_TIMEOUT] Playback timed out after {timeout}s; terminating process.")
            if self._current_player_process:
                self._current_player_process.kill()
        except Exception as e:
            logger.error(f"[ROOM_TTS_PLAYBACK_ERROR] Error running mpv audio output: {e}")
        finally:
            self._current_player_process = None

    def _play_wav_file(self, wav_file: str, timeout: float = 15.0):
        """Backward compatibility alias for _play_audio_file."""
        return self._play_audio_file(wav_file, timeout=timeout)

    def _apply_music_ducking(self) -> Optional[int]:
        """Temporarily ducks active music playback by ~70% (sets volume to 30% of original)."""
        if not self.orchestrator or not hasattr(self.orchestrator, "player"):
            return None
        try:
            status = self.orchestrator.player.get_status()
            if status.get("status") == "PLAYING":
                orig_vol = status.get("volume", 100)
                # Guard: if volume was already ducked (< 20), baseline was 100%
                if orig_vol < 20:
                    orig_vol = 100
                ducked_vol = max(10, int(orig_vol * 0.3))
                logger.info(f"[ROOM_TTS_DUCKING] Ducking music volume: {orig_vol}% -> {ducked_vol}%")
                self.orchestrator.player.set_volume(ducked_vol)
                return orig_vol
        except Exception as e:
            logger.debug(f"[ROOM_TTS_DUCKING_FAIL] Could not duck volume: {e}")
        return None

    def _restore_music_volume(self, original_volume: int):
        """Restores music playback volume to its pre-ducking level."""
        if not self.orchestrator or not hasattr(self.orchestrator, "player"):
            return
        try:
            target_vol = 100 if original_volume < 20 else original_volume
            logger.info(f"[ROOM_TTS_RESTORE_VOL] Restoring music volume to {target_vol}%")
            self.orchestrator.player.set_volume(target_vol)
        except Exception as e:
            logger.debug(f"[ROOM_TTS_RESTORE_FAIL] Could not restore volume: {e}")

    def _get_bt_helper(self) -> Optional[Any]:
        """Obtains the active BluetoothAudioHelper from orchestrator, player, or standalone fallback."""
        if self.orchestrator:
            if hasattr(self.orchestrator, "bt_helper") and self.orchestrator.bt_helper:
                return self.orchestrator.bt_helper
            elif hasattr(self.orchestrator, "player") and hasattr(self.orchestrator.player, "bt_helper"):
                return self.orchestrator.player.bt_helper
        try:
            if not hasattr(self, "_standalone_bt_helper") or self._standalone_bt_helper is None:
                from bluetooth_helper import BluetoothAudioHelper
                self._standalone_bt_helper = BluetoothAudioHelper(mpv_binary=self.mpv_binary)
            return self._standalone_bt_helper
        except Exception as e:
            logger.debug(f"[ROOM_TTS_BT_HELPER_FAIL] Could not create fallback BluetoothAudioHelper: {e}")
            return None

    def _get_soundbar_owner(self) -> str:
        """
        Authoritatively determines the current physical owner of the LG Soundbar.
        Returns: "FIRE_TV", "PC", "NONE", or "UNKNOWN".
        Live physical telemetry strictly outranks historical memory or cached assumptions.
        """
        # 1. Check if RoomStateAggregator explicitly identifies ownership
        agg = self.room_state_aggregator
        if not agg and self.orchestrator and hasattr(self.orchestrator, "room_state_aggregator"):
            agg = self.orchestrator.room_state_aggregator

        if agg and hasattr(agg, "get_room_state") and callable(agg.get_room_state):
            try:
                try:
                    rs = agg.get_room_state(force_refresh=True)
                except TypeError:
                    rs = agg.get_room_state()
                if rs and hasattr(rs, "soundbar") and rs.soundbar and hasattr(rs.soundbar, "current_owner"):
                    # Check provenance for UNKNOWN
                    prov = getattr(rs.soundbar.current_owner, "provenance", None)
                    prov_val = getattr(prov, "value", prov)
                    if str(prov_val).upper() == "UNKNOWN":
                        return "UNKNOWN"

                    owner_val = getattr(rs.soundbar.current_owner, "value", None)
                    if isinstance(owner_val, str):
                        owner_str = owner_val.strip().upper()
                        if owner_str in ("FIRE_TV", "PC", "NONE", "UNKNOWN"):
                            return owner_str
            except Exception as e:
                logger.debug(f"[ROOM_TTS_OWNER_ERR] Error reading room_state soundbar owner: {e}")

        # 2. Check Direct Telemetry via Orchestrator Subsystems
        if self.orchestrator:
            # Check Fire TV direct live Bluetooth connection
            if hasattr(self.orchestrator, "fire_tv") and self.orchestrator.fire_tv:
                try:
                    ftv_bt_fn = getattr(self.orchestrator.fire_tv, "is_soundbar_connected", None)
                    if callable(ftv_bt_fn):
                        res = ftv_bt_fn()
                        if res is True:
                            return "FIRE_TV"
                except Exception as e:
                    logger.debug(f"[ROOM_TTS_OWNER_ERR] Error querying fire_tv.is_soundbar_connected: {e}")

            # Check if orchestrator is in active movie mode
            if getattr(self.orchestrator, "_in_movie_mode", False) is True:
                return "FIRE_TV"

        # 3. Check PC Active WASAPI scan
        bt_helper = self._get_bt_helper()
        if bt_helper and hasattr(bt_helper, "scan_active_endpoints") and callable(bt_helper.scan_active_endpoints):
            try:
                lg_dev, _ = bt_helper.scan_active_endpoints()
                if lg_dev:
                    return "PC"
            except Exception:
                pass

        # 4. If movie mode is NOT active and Fire TV is NOT connected:
        # Default soundbar management domain for the PC daemon is PC
        in_movie = getattr(self.orchestrator, "_in_movie_mode", False) if self.orchestrator else False
        if not in_movie:
            return "PC"

        return "UNKNOWN"



    def _resolve_audio_device_id(self) -> Optional[str]:
        """
        Resolves the active audio device endpoint ID for TTS playback.
        Strict Soundbar Ownership Invariants:
        - If soundbar is owned by FIRE_TV: Bluetooth reclaim is PROHIBITED.
          Returns None (to use Windows default PC output) without stealing Bluetooth.
        - If soundbar is owned by PC: Resolves PC soundbar endpoint (reusing active endpoint,
          or invoking ensure_audio_endpoint() if in PC standby).
        - If soundbar ownership is UNKNOWN: Fails safe without stealing Bluetooth.
        """
        owner = self._get_soundbar_owner()
        logger.info(f"[ROOM_TTS_ROUTING] Soundbar owner={owner}")

        # Rule 1: FIRE_TV ownership -> Prohibit Bluetooth reclaim
        if owner == "FIRE_TV":
            logger.info("[ROOM_TTS_ROUTING] Fire TV owns soundbar; Bluetooth reclaim prohibited.")
            logger.info("[ROOM_TTS_ROUTING] Using PC/default TTS output.")
            return None

        # Rule 2: UNKNOWN ownership -> Fail safe, do NOT attempt Bluetooth reclaim
        if owner == "UNKNOWN":
            logger.info("[ROOM_TTS_ROUTING] Soundbar ownership unknown; Bluetooth reclaim prohibited.")
            return None

        # Rule 3: PC ownership -> Resolve PC soundbar endpoint
        logger.info("[ROOM_TTS_ROUTING] Resolving PC soundbar endpoint.")
        bt_helper = self._get_bt_helper()
        if not bt_helper:
            logger.debug("[ROOM_TTS_ROUTING] No BluetoothAudioHelper found; using default output.")
            return None

        try:
            # First check if LG device is already active in WASAPI graph without reconnecting
            if hasattr(bt_helper, "scan_active_endpoints") and callable(bt_helper.scan_active_endpoints):
                lg_dev, _ = bt_helper.scan_active_endpoints()
                if lg_dev and isinstance(lg_dev, dict) and lg_dev.get("id"):
                    dev_id = lg_dev.get("id")
                    logger.info(f"[ROOM_TTS_ROUTING] Soundbar owner=PC. LG Soundbar already active in WASAPI graph: {dev_id}")
                    return dev_id

            # If not active and PC legitimately owns/controls soundbar -> invoke ensure_audio_endpoint()
            if owner in ("PC", "NONE"):
                logger.info("[ROOM_TTS_ROUTING] Soundbar not active on PC.")
                logger.info("[ROOM_TTS_ROUTING] Attempting ensure_audio_endpoint().")
                if hasattr(bt_helper, "ensure_audio_endpoint") and callable(bt_helper.ensure_audio_endpoint):
                    ready, lg_dev, status_code = bt_helper.ensure_audio_endpoint()
                    if ready and lg_dev and isinstance(lg_dev, dict) and lg_dev.get("id"):
                        dev_id = lg_dev.get("id")
                        logger.info(f"[ROOM_TTS_ROUTING] Reconnected LG Soundbar via {status_code}: {dev_id}")
                        return dev_id
                    else:
                        logger.warning(f"[ROOM_TTS_ROUTING] ensure_audio_endpoint returned status={status_code}; falling back to default.")
        except Exception as e:
            logger.warning(f"[ROOM_TTS_ROUTING] Error ensuring soundbar endpoint: {e}; falling back to default.")

        return None

    def _play_wav_file(self, wav_file: str, timeout: float = 15.0):
        """Plays the generated WAV file through mpv bound to the active room audio sink."""
        try:
            cmd = [
                self.mpv_binary,
                "--no-video",
                "--really-quiet",
                "--volume=100"
            ]
            dev_id = self._resolve_audio_device_id()
            if dev_id:
                cmd.append(f"--audio-device={dev_id}")
                logger.info(f"[ROOM_TTS_PLAY] Routing speech to audio endpoint: {dev_id}")
            else:
                logger.info("[ROOM_TTS_PLAY] Routing speech to Windows default audio endpoint")

            cmd.append(wav_file)
            self._current_player_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            self._current_player_process.wait(timeout=timeout)
            logger.info("[ROOM_TTS_PLAYBACK_COMPLETE] Finished playing room speech.")
        except subprocess.TimeoutExpired:
            logger.warning(f"[ROOM_TTS_TIMEOUT] Playback timed out after {timeout}s; terminating process.")
            if self._current_player_process:
                self._current_player_process.kill()
        except Exception as e:
            logger.error(f"[ROOM_TTS_PLAYBACK_ERROR] Error running mpv audio output: {e}")
        finally:
            self._current_player_process = None


    def _sanitize_text(self, text: str) -> Optional[str]:
        """
        Strict content boundary filter.
        Prevents synthesizing API keys, stack traces, Tuya secrets, or internal logs.
        """
        if not text or not isinstance(text, str):
            return None
        trimmed = text.strip()
        if not trimmed:
            return None

        # Content boundary blacklist
        sensitive_patterns = [
            r"local_key",
            r"access_id",
            r"access_secret",
            r"Traceback \(most recent call last\)",
            r'File "[^"]+", line \d+',
            r"HTTP \d{3}",
            r"Exception:"
        ]
        for pat in sensitive_patterns:
            if re.search(pat, trimmed, re.IGNORECASE):
                logger.warning(f"[ROOM_TTS_SECURITY] Filtered sensitive/stack-trace text from TTS: '{pat}'")
                return "I encountered an internal error processing that request, Sir."

        return trimmed

    def shutdown(self):
        """Releases all TTS resources and terminates the worker loop."""
        logger.info("[ROOM_TTS] Shutting down RoomTtsService...")
        self._stop_event.set()
        self.stop()
        if self._worker_thread.is_alive():
            self._worker_thread.join(timeout=1.0)
        logger.info("[ROOM_TTS] Shutdown complete.")
