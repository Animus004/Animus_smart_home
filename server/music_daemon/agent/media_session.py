"""
Authoritative Media Session Model and Manager for Animus Smart Room.
Tracks persistent media session state across Fire TV and PC audio domains,
coordinates contextual media actions (Play, Pause, Resume, Stop, Skip, Replay),
and resolves contextual references.

EPISTEMIC INVARIANT:
Playback state must reflect verified physical / stream readback.
Media commands dispatch through the canonical capability and execution pipeline.
"""

from __future__ import annotations
import logging
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger("music_daemon.agent.media_session")


class MediaPlaybackState(str, Enum):
    """Authoritative media playback state."""
    STOPPED = "STOPPED"
    PLAYING = "PLAYING"
    PAUSED = "PAUSED"
    BUFFERING = "BUFFERING"
    UNKNOWN = "UNKNOWN"


class MediaSession(BaseModel):
    """Tracks active media playback session metadata and device context."""
    session_id: str = Field(default_factory=lambda: f"media_{uuid.uuid4().hex[:8]}")
    source: str = "FIRE_TV"  # "FIRE_TV" | "PC"
    content_title: Optional[str] = None
    application: Optional[str] = None
    playback_state: MediaPlaybackState = MediaPlaybackState.STOPPED
    volume: Optional[int] = None
    position: Optional[float] = None
    duration: Optional[float] = None
    device_owner: str = "FIRE_TV"
    audio_owner: str = "FIRE_TV"
    started_at: float = Field(default_factory=time.time)
    last_action: Optional[str] = None
    last_action_timestamp: float = Field(default_factory=time.time)


class MediaSessionManager:
    """
    Manages active media session lifecycle and contextual playback commands.
    """

    def __init__(self):
        self.active_session: Optional[MediaSession] = None
        self.session_history: List[MediaSession] = []

    def get_active_session(self) -> Optional[MediaSession]:
        return self.active_session

    def start_session(
        self,
        source: str,
        content_title: Optional[str] = None,
        application: Optional[str] = None,
        device_owner: str = "FIRE_TV",
        audio_owner: str = "FIRE_TV"
    ) -> MediaSession:
        """Starts a new active media session."""
        if self.active_session and self.active_session.playback_state == MediaPlaybackState.PLAYING:
            self.stop_session(reason="NEW_SESSION_STARTED")

        session = MediaSession(
            source=source,
            content_title=content_title,
            application=application,
            playback_state=MediaPlaybackState.PLAYING,
            device_owner=device_owner,
            audio_owner=audio_owner,
            last_action="START",
            last_action_timestamp=time.time()
        )
        self.active_session = session
        logger.info(f"[MEDIA_SESSION_START] Started media session on {source} for '{content_title}' ({application})")
        return session

    def update_state(self, state: MediaPlaybackState, action: Optional[str] = None) -> None:
        """Updates playback state on current session."""
        if self.active_session:
            self.active_session.playback_state = state
            if action:
                self.active_session.last_action = action
            self.active_session.last_action_timestamp = time.time()
            logger.info(f"[MEDIA_SESSION_UPDATE] Session {self.active_session.session_id} state -> {state.value}")

    def pause_session(self) -> Tuple[bool, str]:
        """Marks active session paused."""
        if not self.active_session:
            return False, "NO_ACTIVE_MEDIA_SESSION"
        self.active_session.playback_state = MediaPlaybackState.PAUSED
        self.active_session.last_action = "PAUSE"
        self.active_session.last_action_timestamp = time.time()
        return True, "MEDIA_PAUSED"

    def resume_session(self) -> Tuple[bool, str]:
        """Marks active session resumed."""
        if not self.active_session:
            return False, "NO_ACTIVE_MEDIA_SESSION"
        self.active_session.playback_state = MediaPlaybackState.PLAYING
        self.active_session.last_action = "RESUME"
        self.active_session.last_action_timestamp = time.time()
        return True, "MEDIA_RESUMED"

    def stop_session(self, reason: str = "USER_STOP") -> Tuple[bool, str]:
        """Stops active media session and archives it."""
        if not self.active_session:
            return True, "NO_ACTIVE_MEDIA_SESSION"
        self.active_session.playback_state = MediaPlaybackState.STOPPED
        self.active_session.last_action = f"STOP ({reason})"
        self.active_session.last_action_timestamp = time.time()
        self.session_history.append(self.active_session)
        if len(self.session_history) > 10:
            self.session_history.pop(0)
        self.active_session = None
        return True, "MEDIA_STOPPED"

    def get_status_summary(self) -> Dict[str, Any]:
        """Returns structured dictionary of active media session status."""
        if not self.active_session:
            return {
                "active": False,
                "playback_state": MediaPlaybackState.STOPPED.value,
                "content_title": None,
                "source": None,
                "audio_owner": None
            }
        return {
            "active": True,
            "session_id": self.active_session.session_id,
            "playback_state": self.active_session.playback_state.value,
            "content_title": self.active_session.content_title,
            "application": self.active_session.application,
            "source": self.active_session.source,
            "audio_owner": self.active_session.audio_owner,
            "device_owner": self.active_session.device_owner,
            "last_action": self.active_session.last_action
        }
