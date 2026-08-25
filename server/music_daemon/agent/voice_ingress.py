"""
Authoritative Voice Ingress Adapter for Phase 2 Stage 10 Animus Smart Room.
Provides a clean, decoupled boundary adapter for external voice transcription (STT),
wake-word triggers, and conversational audio transport.

EPISTEMIC & INGRESS INVARIANTS:
1. Voice transport is strictly an ingress adapter feeding text into ConversationEngine.
2. Voice infrastructure NEVER bypasses the canonical planning, validation, or execution pipeline.
3. Decouples microphone hardware / speech recognition providers from deterministic room cognition.
"""

from __future__ import annotations
import logging
import time
from typing import Any, Callable, Dict, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("music_daemon.agent.voice_ingress")


class VoiceTurnPayload(BaseModel):
    """Encapsulates transcribed speech arriving from an external audio interface."""
    transcript: str
    confidence: float = 1.0
    detected_wake_word: Optional[str] = None
    source_client_id: str = "LOCAL_STT"
    timestamp: float = Field(default_factory=time.time)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VoiceIngressAdapter:
    """
    Ingress adapter that receives voice transcripts and feeds them to the Animus conversational brain.
    """

    def __init__(self, on_transcript_received: Optional[Callable[[VoiceTurnPayload], Any]] = None):
        self.on_transcript_received = on_transcript_received
        self.total_ingested_turns: int = 0
        self.last_ingested_payload: Optional[VoiceTurnPayload] = None

    def ingest_transcript(
        self,
        transcript: str,
        confidence: float = 1.0,
        detected_wake_word: Optional[str] = None,
        source_client_id: str = "LOCAL_STT",
        metadata: Optional[Dict[str, Any]] = None
    ) -> VoiceTurnPayload:
        """
        Receives transcribed voice text and packages it for downstream conversational processing.
        """
        clean_text = transcript.strip()
        payload = VoiceTurnPayload(
            transcript=clean_text,
            confidence=confidence,
            detected_wake_word=detected_wake_word,
            source_client_id=source_client_id,
            metadata=metadata or {}
        )
        self.total_ingested_turns += 1
        self.last_ingested_payload = payload

        logger.info(f"[VOICE_INGRESS] Ingested transcript (source={source_client_id}): '{clean_text}'")

        if self.on_transcript_received:
            self.on_transcript_received(payload)

        return payload
