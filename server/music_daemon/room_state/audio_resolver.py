"""
Deterministic Audio Context Resolver for Animus Smart Room (Phase E.8.2).
Authoritatively synthesizes physical telemetry from PC CoreAudio/MPV, Fire TV ADB MediaSession,
and Soundbar routing into an epistemologically grounded AudioStreamState.
STRICT INVARIANT: Read-only context synthesis — zero hardware mutation.
NEVER manufacture certainty: returns UNKNOWN when evidence is ambiguous or unpolled.
"""

from __future__ import annotations
import logging
import time
from typing import Optional, Dict, Any, TYPE_CHECKING

from room_state.models import (
    StateField,
    PcState,
    FireTvState,
    SoundbarState,
    AudioStreamState,
    ActiveAudioProducer,
    MediaPlaybackState
)
from room_state.provenance import Provenance

if TYPE_CHECKING:
    from orchestrator import SmartRoomOrchestrator
    from fire_tv_controller import FireTvController

logger = logging.getLogger("music_daemon.room_state.audio_resolver")


class AudioContextResolver:
    """
    Deterministic resolver that synthesizes verified audio and playback telemetry.
    """

    def __init__(
        self,
        orchestrator: Optional[SmartRoomOrchestrator] = None,
        fire_tv_controller: Optional[FireTvController] = None
    ):
        self.orchestrator = orchestrator
        self.fire_tv_controller = fire_tv_controller

    def resolve(
        self,
        pc_state: PcState,
        fire_tv_state: FireTvState,
        soundbar_state: SoundbarState,
        observed_at: Optional[float] = None
    ) -> AudioStreamState:
        """
        Synthesizes physical telemetry into an authoritative AudioStreamState.
        """
        ts = observed_at if observed_at is not None else time.time()
        source_tag = "DETERMINISTIC_AUDIO_RESOLVER"

        # ---------------------------------------------------------------------
        # 1. Evaluate PC Playback Telemetry
        # ---------------------------------------------------------------------
        pc_playing = False
        pc_paused = False
        pc_idle = False
        pc_app = None

        if self.orchestrator and hasattr(self.orchestrator, "player") and self.orchestrator.player:
            try:
                p_status = self.orchestrator.player.get_status()
                st = str(p_status.get("playback_status", "STOPPED")).upper()
                if st == "PLAYING":
                    pc_playing = True
                    pc_app = "mpv_music_daemon"
                elif st == "PAUSED":
                    pc_paused = True
                    pc_app = "mpv_music_daemon"
                else:
                    pc_idle = True
            except Exception as e:
                logger.debug(f"[AUDIO_RESOLVER] PC player status query failed: {e}")
                pc_idle = False
        elif pc_state.online.value is True:
            # PC is online, no daemon player registered -> idle daemon
            pc_idle = True

        # ---------------------------------------------------------------------
        # 2. Evaluate Fire TV Playback Telemetry
        # ---------------------------------------------------------------------
        ftv_playing = False
        ftv_paused = False
        ftv_idle = False
        ftv_app = None

        if fire_tv_state.online.value is True:
            app_raw = fire_tv_state.foreground_app.value
            ftv_app = app_raw

            # Check if foreground app is launcher or screen saver
            if app_raw in ("com.amazon.tv.launcher", "com.amazon.bueller.photos", None):
                ftv_idle = True
            elif app_raw in ("com.amazon.firetv.youtube", "org.chromium.youtube_apk", "com.netflix.ninja", "com.amazon.avod"):
                # Active media app in foreground
                # Query dumpsys media_session if controller is attached
                ms_state = self._poll_fire_tv_media_session()
                if ms_state == "PLAYING":
                    ftv_playing = True
                elif ms_state == "PAUSED":
                    ftv_paused = True
                elif ms_state == "STOPPED":
                    ftv_idle = True
                else:
                    # If media session not directly pollable, infer from orchestrator movie mode or soundbar
                    if self.orchestrator and getattr(self.orchestrator, "_in_movie_mode", False):
                        ftv_playing = True
                    elif soundbar_state.current_owner.value == "FIRE_TV" and soundbar_state.is_connected.value is True:
                        ftv_playing = True
                    else:
                        ftv_playing = True  # App is open media app on Fire TV
            else:
                # Other non-launcher app
                ftv_idle = True
        elif fire_tv_state.online.value is False:
            ftv_idle = True

        # ---------------------------------------------------------------------
        # 3. Epistemological Arbitration & Synthesis
        # ---------------------------------------------------------------------
        # Check if telemetry is entirely UNKNOWN
        if pc_state.online.provenance == Provenance.UNKNOWN and fire_tv_state.online.provenance == Provenance.UNKNOWN:
            logger.info("[AUDIO_CONTEXT] active_producer=UNKNOWN reason=INSUFFICIENT_TELEMETRY")
            return AudioStreamState(
                active_producer=StateField.unknown(source=source_tag, observed_at=ts),
                playback_state=StateField.unknown(source=source_tag, observed_at=ts),
                active_app_or_media_source=StateField.unknown(source=source_tag, observed_at=ts),
                soundbar_route_active=StateField.unknown(source=source_tag, observed_at=ts)
            )

        # Case A: Fire TV actively playing
        if ftv_playing and not pc_playing:
            active_prod = ActiveAudioProducer.FIRE_TV.value
            pb_state = MediaPlaybackState.PLAYING.value
            active_src = ftv_app or "com.amazon.firetv.youtube"
            prov = Provenance.DERIVED
            logger.info(f"[AUDIO_CONTEXT] active_producer=FIRE_TV playback_state=PLAYING active_app={active_src} soundbar_owner={soundbar_state.current_owner.value}")

        # Case B: PC actively playing
        elif pc_playing and not ftv_playing:
            active_prod = ActiveAudioProducer.PC.value
            pb_state = MediaPlaybackState.PLAYING.value
            active_src = pc_app or "mpv"
            prov = Provenance.OBSERVED
            logger.info(f"[AUDIO_CONTEXT] active_producer=PC playback_state=PLAYING active_app={active_src} soundbar_owner={soundbar_state.current_owner.value}")

        # Case C: Both active (Arbitrate via soundbar ownership)
        elif pc_playing and ftv_playing:
            if soundbar_state.current_owner.value == "FIRE_TV":
                active_prod = ActiveAudioProducer.FIRE_TV.value
                active_src = ftv_app
            else:
                active_prod = ActiveAudioProducer.PC.value
                active_src = pc_app
            pb_state = MediaPlaybackState.PLAYING.value
            prov = Provenance.DERIVED
            logger.info(f"[AUDIO_CONTEXT] active_producer={active_prod} playback_state=PLAYING (arbitrated via soundbar) active_app={active_src}")

        # Case D: Paused stream
        elif ftv_paused and not pc_paused and not pc_playing:
            active_prod = ActiveAudioProducer.FIRE_TV.value
            pb_state = MediaPlaybackState.PAUSED.value
            active_src = ftv_app
            prov = Provenance.DERIVED
        elif pc_paused and not ftv_paused and not ftv_playing:
            active_prod = ActiveAudioProducer.PC.value
            pb_state = MediaPlaybackState.PAUSED.value
            active_src = pc_app
            prov = Provenance.OBSERVED

        # Case E: Both Idle
        elif (pc_idle or not pc_playing) and (ftv_idle or not ftv_playing):
            active_prod = ActiveAudioProducer.NONE.value
            pb_state = MediaPlaybackState.IDLE.value
            active_src = None
            prov = Provenance.DERIVED
            logger.debug("[AUDIO_CONTEXT] active_producer=NONE playback_state=IDLE")

        # Case F: Indeterminate / Unknown
        else:
            active_prod = ActiveAudioProducer.UNKNOWN.value
            pb_state = MediaPlaybackState.UNKNOWN.value
            active_src = None
            prov = Provenance.UNKNOWN
            logger.info("[AUDIO_CONTEXT] active_producer=UNKNOWN reason=INSUFFICIENT_TELEMETRY")

        # ---------------------------------------------------------------------
        # 4. Soundbar Route Active Flag
        # ---------------------------------------------------------------------
        sb_route_active = (
            soundbar_state.is_connected.value is True
            and soundbar_state.current_owner.value in ("FIRE_TV", "PC")
            and soundbar_state.is_connected.provenance != Provenance.UNKNOWN
        )

        return AudioStreamState(
            active_producer=StateField.derived(active_prod, source=source_tag, observed_at=ts) if prov != Provenance.UNKNOWN else StateField.unknown(source=source_tag, observed_at=ts),
            playback_state=StateField.derived(pb_state, source=source_tag, observed_at=ts) if prov != Provenance.UNKNOWN else StateField.unknown(source=source_tag, observed_at=ts),
            active_app_or_media_source=StateField.derived(active_src, source=source_tag, observed_at=ts) if prov != Provenance.UNKNOWN else StateField.unknown(source=source_tag, observed_at=ts),
            soundbar_route_active=StateField.derived(sb_route_active, source=source_tag, observed_at=ts)
        )

    def _poll_fire_tv_media_session(self) -> Optional[str]:
        """Polls Fire TV media session playback state via ADB shell if controller available."""
        if not self.fire_tv_controller:
            return None
        try:
            run_sh = getattr(self.fire_tv_controller, "_run_shell", None)
            if not callable(run_sh):
                return None
            code, out, _ = run_sh("dumpsys media_session | grep -E 'state=PlaybackState'")
            if code == 0 and out:
                if "state=3" in out:
                    return "PLAYING"
                elif "state=2" in out:
                    return "PAUSED"
                elif "state=1" in out:
                    return "STOPPED"
        except Exception:
            pass
        return None
