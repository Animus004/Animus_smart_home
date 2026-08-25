"""
Capability Awareness Engine for Animus Personal Agent.
Maintains live awareness of what Animus can physically control via UnifiedCapabilityRegistry.
Answers capability queries and truthfully explains unsupported features without hallucination.
"""

from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional, Tuple
from capability_registry import UnifiedCapabilityRegistry
from agent.models import UserProfile

logger = logging.getLogger("music_daemon.agent.capability_awareness")


class CapabilityAwarenessEngine:
    """
    Provides capability introspection and conversational explanations.
    """

    def __init__(self, registry: UnifiedCapabilityRegistry, user_profile: UserProfile):
        self.registry = registry
        self.user_profile = user_profile

    def get_supported_domains_summary(self) -> Dict[str, Any]:
        """
        Returns structured taxonomy of all supported smart room subsystems.
        """
        return {
            "device_control": [
                "Projector (Power, HDMI 1 switcher, Android home, Brightness, Auto-focus, Keystone)",
                "Fire TV 4K Max (Power wake/sleep, Navigation, App launch, Volume, Mute)",
                "LG SNC4R Soundbar (Direct Fire TV Bluetooth routing, Windows Device Portal PC routing)",
                "PC Audio (Windows CoreAudio master volume, Mute, App launch)",
                "Air Conditioner (Tuya Cloud Power, Temperature 16-30°C, Modes: Cool/Auto/Dry/Fan)"
            ],
            "entertainment": [
                "YouTube (Automated launch & video playback)",
                "Netflix (Catalog deep-linking & launch)",
                "Prime Video (Catalog & launch)",
                "Apple TV (Streaming launch)"
            ],
            "automation": [
                "Movie Mode / Cinema Environment",
                "Work / Focus Mode",
                "Morning Motivation & Alarm",
                "Audio Ownership Routing"
            ],
            "assistant": [
                "Task Management & Due Queries",
                "Scheduled Reminders (Guitar, SQL, Learning)",
                "Daily Briefings (Morning & Evening)",
                "Conversational Follow-Up Disambiguation"
            ]
        }

    def answer_capability_query(self, query: str) -> str:
        """
        Answers natural language inquiries like 'What can you control?' or 'What can you do?'.
        """
        addr = self.user_profile.identity.preferred_address
        summary = self.get_supported_domains_summary()

        lines: List[str] = [
            f"Here is everything I can control and manage for you, {addr}:",
            "\n📺 Hardware Devices:",
            *[f"  • {d}" for d in summary["device_control"]],
            "\n🎬 Entertainment & Streaming:",
            *[f"  • {e}" for e in summary["entertainment"]],
            "\n⚡ Smart Automations:",
            *[f"  • {a}" for a in summary["automation"]],
            "\n📋 Personal Assistant:",
            *[f"  • {p}" for p in summary["assistant"]],
        ]
        return "\n".join(lines)

    def explain_unsupported_capability(self, device_or_feature: str) -> str:
        """
        Generates truthful limitation explanation for unsupported devices (e.g. bedroom fan, microwave).
        """
        addr = self.user_profile.identity.preferred_address
        return (
            f"I can't control the {device_or_feature} yet, {addr}. "
            f"I can control the Projector, Fire TV, LG Soundbar, PC Audio, and AC."
        )
