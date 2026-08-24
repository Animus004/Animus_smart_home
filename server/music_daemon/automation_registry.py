"""
Authoritative Automation Registry for Animus Smart Room Fire TV Subsystem.
Provides a machine-readable, declarative registry of all 67 service use-cases across 7 categories
with explicit capability requirements, preconditions, execution steps, verification strategies,
fallbacks, latency estimations, and risk classifications.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List

logger = logging.getLogger("music_daemon.automation_registry")


class AutomationCategory(str, Enum):
    CINEMA = "CINEMA"
    STREAMING = "STREAMING"
    AUDIO = "AUDIO"
    PROJECTOR = "PROJECTOR"
    INTERRUPTION = "INTERRUPTION"
    LIFECYCLE = "LIFECYCLE"
    RECOVERY = "RECOVERY"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass
class AutomationMetadata:
    automation_id: str
    category: AutomationCategory
    name: str
    description: str
    required_capabilities: List[str]
    optional_capabilities: List[str] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)
    steps: List[str] = field(default_factory=list)
    verification: str = ""
    fallback: str = ""
    estimated_latency_ms: int = 1000
    risk_level: RiskLevel = RiskLevel.LOW
    parameters_schema: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "automation_id": self.automation_id,
            "category": self.category.value,
            "name": self.name,
            "description": self.description,
            "required_capabilities": self.required_capabilities,
            "optional_capabilities": self.optional_capabilities,
            "preconditions": self.preconditions,
            "steps": self.steps,
            "verification": self.verification,
            "fallback": self.fallback,
            "estimated_latency_ms": self.estimated_latency_ms,
            "risk_level": self.risk_level.value,
            "parameters_schema": self.parameters_schema
        }


class AutomationRegistry:
    """
    Central repository of all 67 declarative automations across 7 families.
    """

    def __init__(self):
        self._automations: Dict[str, AutomationMetadata] = {}
        self._register_all_automations()

    def register(self, automation: AutomationMetadata):
        self._automations[automation.automation_id] = automation

    def get(self, automation_id: str) -> Optional[AutomationMetadata]:
        return self._automations.get(automation_id)

    def list_all(self) -> List[AutomationMetadata]:
        return list(self._automations.values())

    def list_by_category(self, category: AutomationCategory) -> List[AutomationMetadata]:
        return [a for a in self._automations.values() if a.category == category]

    def count(self) -> int:
        return len(self._automations)

    def _register_all_automations(self):
        # ======================================================================
        # A. CINEMA (1–15)
        # ======================================================================
        self.register(AutomationMetadata(
            automation_id="start_cinema",
            category=AutomationCategory.CINEMA,
            name="Start Cinema",
            description="Complete cinema workflow: wakes Fire TV, switches projector to HDMI 1, releases PC audio, connects soundbar directly to Fire TV, and launches content.",
            required_capabilities=["power_wake", "projector_switch_hdmi1", "audio_switch_to_fire_tv", "media_direct_provider"],
            preconditions=["fire_tv_reachable", "projector_powered_on"],
            steps=["wake_fire_tv", "switch_projector_hdmi1", "release_pc_audio", "connect_soundbar_direct", "resolve_content", "launch_content_direct"],
            verification="projector HDMI1 active AND Fire TV A2DP connected AND target provider foreground",
            fallback="Settings+DPAD BT fallback, provider UI fallback",
            estimated_latency_ms=2500,
            risk_level=RiskLevel.MEDIUM,
            parameters_schema={"content": "string (optional)", "provider": "string (optional)"}
        ))

        self.register(AutomationMetadata(
            automation_id="stop_cinema",
            category=AutomationCategory.CINEMA,
            name="Stop Cinema",
            description="Stops cinema playback, disconnects soundbar from Fire TV, restores audio to PC, and optionally shuts down projector.",
            required_capabilities=["media_pause", "audio_switch_to_pc"],
            steps=["pause_media", "disconnect_soundbar_direct", "restore_pc_audio"],
            verification="Fire TV paused AND Soundbar disconnected from Fire TV AND PC audio ready",
            estimated_latency_ms=1800,
            risk_level=RiskLevel.LOW,
            parameters_schema={"turn_off_projector": "boolean (default: false)"}
        ))

        self.register(AutomationMetadata(
            automation_id="pause_cinema",
            category=AutomationCategory.CINEMA,
            name="Pause Cinema",
            description="Pauses active media playback on Fire TV.",
            required_capabilities=["media_pause"],
            steps=["send_media_pause"],
            verification="media session state PAUSED",
            estimated_latency_ms=200,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="resume_cinema",
            category=AutomationCategory.CINEMA,
            name="Resume Cinema",
            description="Resumes paused media playback on Fire TV.",
            required_capabilities=["media_play"],
            steps=["send_media_play"],
            verification="media session state PLAYING",
            estimated_latency_ms=200,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="switch_movie_provider",
            category=AutomationCategory.CINEMA,
            name="Switch Movie Provider",
            description="Switches from current streaming provider to a new provider, seamlessly retargeting content.",
            required_capabilities=["media_direct_provider"],
            steps=["pause_current_provider", "resolve_target_provider", "launch_target_provider"],
            verification="target provider foreground",
            estimated_latency_ms=600,
            risk_level=RiskLevel.LOW,
            parameters_schema={"target_provider": "string (required)", "content": "string (optional)"}
        ))

        self.register(AutomationMetadata(
            automation_id="watch_youtube_movie",
            category=AutomationCategory.CINEMA,
            name="Watch YouTube Movie",
            description="Directly launches YouTube content or video ID with verified instant autoplay.",
            required_capabilities=["media_direct_youtube", "audio_switch_to_fire_tv"],
            steps=["ensure_cinema_prerequisites", "launch_youtube_direct"],
            verification="YouTube foreground AND playback state PLAYING",
            estimated_latency_ms=1200,
            risk_level=RiskLevel.LOW,
            parameters_schema={"query": "string (required)"}
        ))

        self.register(AutomationMetadata(
            automation_id="watch_netflix_movie",
            category=AutomationCategory.CINEMA,
            name="Watch Netflix Movie",
            description="Deep links directly to Netflix title or content page.",
            required_capabilities=["media_direct_provider", "audio_switch_to_fire_tv"],
            steps=["ensure_cinema_prerequisites", "launch_netflix_title_page"],
            verification="Netflix foreground AND content page opened",
            estimated_latency_ms=1400,
            risk_level=RiskLevel.LOW,
            parameters_schema={"title_id": "string (required)"}
        ))

        self.register(AutomationMetadata(
            automation_id="watch_prime_movie",
            category=AutomationCategory.CINEMA,
            name="Watch Prime Movie",
            description="Directly opens Prime Video slate to content page.",
            required_capabilities=["media_direct_provider", "audio_switch_to_fire_tv"],
            steps=["ensure_cinema_prerequisites", "launch_prime_content_page"],
            verification="Prime Video foreground AND content page opened",
            estimated_latency_ms=1400,
            risk_level=RiskLevel.LOW,
            parameters_schema={"asin": "string (required)"}
        ))

        self.register(AutomationMetadata(
            automation_id="watch_apple_tv_movie",
            category=AutomationCategory.CINEMA,
            name="Watch Apple TV Movie",
            description="Deep links directly to Apple TV content page.",
            required_capabilities=["media_direct_provider", "audio_switch_to_fire_tv"],
            steps=["ensure_cinema_prerequisites", "launch_apple_tv_content_page"],
            verification="Apple TV foreground AND content page opened",
            estimated_latency_ms=1400,
            risk_level=RiskLevel.LOW,
            parameters_schema={"content_id": "string (required)"}
        ))

        self.register(AutomationMetadata(
            automation_id="watch_hotstar_movie",
            category=AutomationCategory.CINEMA,
            name="Watch Hotstar Movie",
            description="Directly opens JioHotstar content with verified autoplay.",
            required_capabilities=["media_direct_provider", "audio_switch_to_fire_tv"],
            steps=["ensure_cinema_prerequisites", "launch_hotstar_content"],
            verification="JioHotstar foreground",
            estimated_latency_ms=1300,
            risk_level=RiskLevel.LOW,
            parameters_schema={"content_id": "string (required)"}
        ))

        self.register(AutomationMetadata(
            automation_id="watch_zee5_movie",
            category=AutomationCategory.CINEMA,
            name="Watch Zee5 Movie",
            description="Directly opens Zee5 movie details page.",
            required_capabilities=["media_direct_provider", "audio_switch_to_fire_tv"],
            steps=["ensure_cinema_prerequisites", "launch_zee5_content"],
            verification="Zee5 foreground",
            estimated_latency_ms=1300,
            risk_level=RiskLevel.LOW,
            parameters_schema={"content_id": "string (required)"}
        ))

        self.register(AutomationMetadata(
            automation_id="resume_last_movie",
            category=AutomationCategory.CINEMA,
            name="Resume Last Movie",
            description="Brings last active streaming provider to foreground and issues resume play command.",
            required_capabilities=["media_play", "app_get_foreground"],
            steps=["detect_last_provider", "bring_to_foreground", "send_media_play"],
            verification="media session state PLAYING",
            estimated_latency_ms=500,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="replay_last_content",
            category=AutomationCategory.CINEMA,
            name="Replay Last Content",
            description="Restarts current or previous content from the beginning.",
            required_capabilities=["media_previous", "media_play"],
            steps=["send_media_previous", "send_media_play"],
            verification="media session state PLAYING",
            estimated_latency_ms=400,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="recover_stuck_movie",
            category=AutomationCategory.CINEMA,
            name="Recover Stuck Movie",
            description="Self-heals a frozen or unresponsive streaming app by force-restarting package and re-verifying A2DP.",
            required_capabilities=["app_get_foreground", "media_direct_provider", "bt_connect_soundbar_direct"],
            steps=["force_stop_app", "reconnect_soundbar_if_lost", "relaunch_provider_content"],
            verification="provider foreground AND A2DP active",
            estimated_latency_ms=2200,
            risk_level=RiskLevel.MEDIUM
        ))

        self.register(AutomationMetadata(
            automation_id="cinema_shutdown",
            category=AutomationCategory.CINEMA,
            name="Cinema Shutdown",
            description="Full entertainment shutdown: stops playback, disconnects soundbar, puts Fire TV to sleep, and shuts down projector safely.",
            required_capabilities=["media_stop", "power_sleep", "projector_switch_hdmi1", "audio_switch_to_pc"],
            steps=["stop_media", "disconnect_soundbar", "sleep_fire_tv", "turn_off_projector", "restore_pc_audio"],
            verification="Fire TV asleep AND projector powered off AND PC audio restored",
            estimated_latency_ms=3000,
            risk_level=RiskLevel.MEDIUM
        ))

        # ======================================================================
        # B. STREAMING (16–27)
        # ======================================================================
        self.register(AutomationMetadata(
            automation_id="open_youtube",
            category=AutomationCategory.STREAMING,
            name="Open YouTube",
            description="Opens YouTube Leanback UI without changing audio route or projector if already set.",
            required_capabilities=["app_launch_youtube"],
            steps=["launch_youtube_app"],
            verification="YouTube foreground",
            estimated_latency_ms=300,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="open_netflix",
            category=AutomationCategory.STREAMING,
            name="Open Netflix",
            description="Opens Netflix TV application.",
            required_capabilities=["media_direct_provider"],
            steps=["launch_netflix_app"],
            verification="Netflix foreground",
            estimated_latency_ms=400,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="open_prime_video",
            category=AutomationCategory.STREAMING,
            name="Open Prime Video",
            description="Opens Prime Video Slate application.",
            required_capabilities=["media_direct_provider"],
            steps=["launch_prime_app"],
            verification="Prime Video foreground",
            estimated_latency_ms=400,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="open_apple_tv",
            category=AutomationCategory.STREAMING,
            name="Open Apple TV",
            description="Opens Apple TV application.",
            required_capabilities=["media_direct_provider"],
            steps=["launch_apple_tv_app"],
            verification="Apple TV foreground",
            estimated_latency_ms=400,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="open_hotstar",
            category=AutomationCategory.STREAMING,
            name="Open Hotstar",
            description="Opens JioHotstar TV application.",
            required_capabilities=["media_direct_provider"],
            steps=["launch_hotstar_app"],
            verification="JioHotstar foreground",
            estimated_latency_ms=400,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="open_zee5",
            category=AutomationCategory.STREAMING,
            name="Open Zee5",
            description="Opens Zee5 TV application.",
            required_capabilities=["media_direct_provider"],
            steps=["launch_zee5_app"],
            verification="Zee5 foreground",
            estimated_latency_ms=400,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="switch_netflix_to_youtube",
            category=AutomationCategory.STREAMING,
            name="Switch Netflix → YouTube",
            description="Transitions active foreground from Netflix to YouTube.",
            required_capabilities=["app_launch_youtube"],
            steps=["launch_youtube_app"],
            verification="YouTube foreground",
            estimated_latency_ms=350,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="switch_youtube_to_netflix",
            category=AutomationCategory.STREAMING,
            name="Switch YouTube → Netflix",
            description="Transitions active foreground from YouTube to Netflix.",
            required_capabilities=["media_direct_provider"],
            steps=["launch_netflix_app"],
            verification="Netflix foreground",
            estimated_latency_ms=400,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="switch_prime_to_youtube",
            category=AutomationCategory.STREAMING,
            name="Switch Prime → YouTube",
            description="Transitions active foreground from Prime Video to YouTube.",
            required_capabilities=["app_launch_youtube"],
            steps=["launch_youtube_app"],
            verification="YouTube foreground",
            estimated_latency_ms=350,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="switch_provider_preserve_display",
            category=AutomationCategory.STREAMING,
            name="Switch Provider Preserve Display",
            description="Switches streaming applications while guaranteeing projector input remains untouched.",
            required_capabilities=["media_direct_provider"],
            steps=["launch_target_provider"],
            verification="target provider foreground AND projector HDMI1 unchanged",
            estimated_latency_ms=400,
            risk_level=RiskLevel.LOW,
            parameters_schema={"target_provider": "string (required)"}
        ))

        self.register(AutomationMetadata(
            automation_id="open_provider_preserve_audio",
            category=AutomationCategory.STREAMING,
            name="Open Provider Preserve Audio",
            description="Opens streaming application without modifying current audio ownership.",
            required_capabilities=["media_direct_provider"],
            steps=["launch_target_provider"],
            verification="target provider foreground AND audio state unchanged",
            estimated_latency_ms=400,
            risk_level=RiskLevel.LOW,
            parameters_schema={"target_provider": "string (required)"}
        ))

        self.register(AutomationMetadata(
            automation_id="return_to_previous_provider",
            category=AutomationCategory.STREAMING,
            name="Return To Previous Provider",
            description="Returns to previously active foreground streaming application.",
            required_capabilities=["navigation_back", "app_get_foreground"],
            steps=["send_nav_back", "verify_foreground"],
            verification="previous provider foreground",
            estimated_latency_ms=300,
            risk_level=RiskLevel.LOW
        ))

        # ======================================================================
        # C. AUDIO (28–37)
        # ======================================================================
        self.register(AutomationMetadata(
            automation_id="route_audio_to_fire_tv",
            category=AutomationCategory.AUDIO,
            name="Route Audio To Fire TV",
            description="Transfers LG Soundbar ownership from PC to Fire TV using direct Bluetooth helper.",
            required_capabilities=["audio_switch_to_fire_tv"],
            steps=["release_pc_audio", "connect_fire_tv_soundbar_direct"],
            verification="Fire TV A2DP connected (54:15:89:DC:A5:79)",
            fallback="Fire TV Settings+DPAD Bluetooth connect",
            estimated_latency_ms=1400,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="route_audio_to_pc",
            category=AutomationCategory.AUDIO,
            name="Route Audio To PC",
            description="Transfers LG Soundbar ownership from Fire TV back to PC via Windows Device Portal.",
            required_capabilities=["audio_switch_to_pc"],
            steps=["disconnect_fire_tv_soundbar_direct", "connect_pc_soundbar"],
            verification="PC soundbar status AUDIO_READY",
            estimated_latency_ms=2500,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="connect_soundbar",
            category=AutomationCategory.AUDIO,
            name="Connect Soundbar",
            description="Ensures LG Soundbar is connected to active entertainment host.",
            required_capabilities=["bt_connect_soundbar_direct"],
            steps=["detect_active_host", "connect_soundbar_to_host"],
            verification="Soundbar A2DP connected",
            estimated_latency_ms=1200,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="disconnect_soundbar",
            category=AutomationCategory.AUDIO,
            name="Disconnect Soundbar",
            description="Disconnects soundbar from current active host.",
            required_capabilities=["bt_disconnect_soundbar_direct"],
            steps=["disconnect_soundbar_from_active_host"],
            verification="Soundbar disconnected",
            estimated_latency_ms=500,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="recover_soundbar",
            category=AutomationCategory.AUDIO,
            name="Recover Soundbar",
            description="Forcefully clears stale Bluetooth audio sessions across PC and Fire TV and re-establishes clean link.",
            required_capabilities=["audio_switch_to_pc", "audio_switch_to_fire_tv"],
            steps=["disconnect_all_hosts", "sleep_briefly", "connect_target_host"],
            verification="target host A2DP connected",
            estimated_latency_ms=3500,
            risk_level=RiskLevel.MEDIUM,
            parameters_schema={"target_host": "string (optional: 'FIRE_TV' | 'PC')"}
        ))

        self.register(AutomationMetadata(
            automation_id="verify_soundbar",
            category=AutomationCategory.AUDIO,
            name="Verify Soundbar",
            description="Queries authoritative physical Bluetooth status across PC and Fire TV.",
            required_capabilities=["bt_get_status"],
            steps=["query_fire_tv_bt_telemetry", "query_pc_audio_telemetry"],
            verification="live audio device state returned",
            estimated_latency_ms=200,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="emergency_mute",
            category=AutomationCategory.AUDIO,
            name="Emergency Mute",
            description="Immediately mutes volume across both PC and Fire TV subsystems.",
            required_capabilities=["mute"],
            steps=["send_fire_tv_mute", "mute_pc_player"],
            verification="all active streams muted",
            estimated_latency_ms=150,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="restore_audio",
            category=AutomationCategory.AUDIO,
            name="Restore Audio",
            description="Unmutes and restores nominal listening volume.",
            required_capabilities=["mute", "volume_up"],
            steps=["unmute_fire_tv", "unmute_pc_player"],
            verification="audio unmuted",
            estimated_latency_ms=200,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="audio_handoff_pc_to_fire_tv",
            category=AutomationCategory.AUDIO,
            name="Audio Handoff PC → Fire TV",
            description="Gracefully pauses PC audio playback and transfers LG Soundbar ownership to Fire TV.",
            required_capabilities=["audio_switch_to_fire_tv"],
            steps=["pause_pc_player", "transfer_soundbar_to_fire_tv"],
            verification="Fire TV A2DP connected",
            estimated_latency_ms=1500,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="audio_handoff_fire_tv_to_pc",
            category=AutomationCategory.AUDIO,
            name="Audio Handoff Fire TV → PC",
            description="Gracefully pauses Fire TV playback and transfers LG Soundbar ownership back to PC.",
            required_capabilities=["media_pause", "audio_switch_to_pc"],
            steps=["pause_fire_tv_media", "transfer_soundbar_to_pc"],
            verification="PC soundbar status AUDIO_READY",
            estimated_latency_ms=2600,
            risk_level=RiskLevel.LOW
        ))

        # ======================================================================
        # D. PROJECTOR (38–44)
        # ======================================================================
        self.register(AutomationMetadata(
            automation_id="projector_fire_tv_mode",
            category=AutomationCategory.PROJECTOR,
            name="Projector Fire TV Mode",
            description="Ensures projector is powered on and actively displaying Fire TV on HDMI 1.",
            required_capabilities=["projector_switch_hdmi1"],
            steps=["verify_projector_power", "switch_source_hdmi1"],
            verification="projector input source HDMI 1",
            estimated_latency_ms=500,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="projector_pc_mode",
            category=AutomationCategory.PROJECTOR,
            name="Projector PC Mode",
            description="Switches projector display mode for PC desktop workstation use.",
            required_capabilities=["projector_switch_hdmi1"],
            steps=["switch_projector_source_pc"],
            verification="projector input source PC",
            estimated_latency_ms=500,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="reassert_hdmi1",
            category=AutomationCategory.PROJECTOR,
            name="Reassert HDMI 1",
            description="Re-enforces HDMI 1 input source if projector input drifted.",
            required_capabilities=["projector_switch_hdmi1"],
            steps=["send_hdmi1_keysequence"],
            verification="projector input source HDMI 1",
            estimated_latency_ms=400,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="recover_hdmi",
            category=AutomationCategory.PROJECTOR,
            name="Recover HDMI",
            description="Self-heals lost HDMI video handshake between Fire TV and Projector.",
            required_capabilities=["projector_switch_hdmi1", "navigation_home"],
            steps=["cycle_hdmi1_source", "send_fire_tv_wake_key"],
            verification="projector input HDMI 1 AND Fire TV responsive",
            estimated_latency_ms=1200,
            risk_level=RiskLevel.MEDIUM
        ))

        self.register(AutomationMetadata(
            automation_id="safe_projector_shutdown",
            category=AutomationCategory.PROJECTOR,
            name="Safe Projector Shutdown",
            description="Powers off the projector safely with OEM confirmation prompt handling.",
            required_capabilities=["projector_switch_hdmi1"],
            steps=["send_power_off_sequence"],
            verification="projector power state OFF",
            estimated_latency_ms=1500,
            risk_level=RiskLevel.MEDIUM
        ))

        self.register(AutomationMetadata(
            automation_id="prepare_cinema_display",
            category=AutomationCategory.PROJECTOR,
            name="Prepare Cinema Display",
            description="Validates projector readiness, active HDMI 1 connection, and display resolution.",
            required_capabilities=["projector_switch_hdmi1"],
            steps=["verify_projector_on", "ensure_hdmi1"],
            verification="projector ready for cinema",
            estimated_latency_ms=400,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="prepare_work_display",
            category=AutomationCategory.PROJECTOR,
            name="Prepare Work Display",
            description="Configures room display environment for workstation focus.",
            required_capabilities=["projector_switch_hdmi1"],
            steps=["configure_work_display"],
            verification="display ready for work",
            estimated_latency_ms=400,
            risk_level=RiskLevel.LOW
        ))

        # ======================================================================
        # E. INTERRUPTION / RESUME (45–53)
        # ======================================================================
        self.register(AutomationMetadata(
            automation_id="quick_break",
            category=AutomationCategory.INTERRUPTION,
            name="Quick Break",
            description="Pauses cinema media, preserves audio connection, and dims lights for a temporary pause.",
            required_capabilities=["media_pause"],
            steps=["send_media_pause"],
            verification="media state PAUSED",
            estimated_latency_ms=250,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="resume_after_break",
            category=AutomationCategory.INTERRUPTION,
            name="Resume After Break",
            description="Resumes cinema media after a quick break, ensuring A2DP audio link is intact.",
            required_capabilities=["media_play", "bt_is_soundbar_connected"],
            steps=["verify_a2dp_connected", "send_media_play"],
            verification="media state PLAYING AND A2DP connected",
            estimated_latency_ms=400,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="pause_for_phone_call",
            category=AutomationCategory.INTERRUPTION,
            name="Pause For Phone Call",
            description="Instantly pauses all playback and mutes room audio for an incoming phone call.",
            required_capabilities=["media_pause", "mute"],
            steps=["pause_all_media", "mute_room_audio"],
            verification="all media PAUSED AND audio MUTED",
            estimated_latency_ms=200,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="resume_after_phone_call",
            category=AutomationCategory.INTERRUPTION,
            name="Resume After Phone Call",
            description="Restores volume and resumes playback after a phone call.",
            required_capabilities=["mute", "media_play"],
            steps=["unmute_room_audio", "send_media_play"],
            verification="audio unmuted AND media PLAYING",
            estimated_latency_ms=300,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="stop_entertainment_return_to_work",
            category=AutomationCategory.INTERRUPTION,
            name="Stop Entertainment And Return To Work",
            description="Stops movie, returns soundbar to PC, and prepares workstation audio.",
            required_capabilities=["media_stop", "audio_switch_to_pc"],
            steps=["stop_fire_tv_media", "disconnect_fire_tv_soundbar", "connect_pc_soundbar"],
            verification="PC soundbar AUDIO_READY",
            estimated_latency_ms=2600,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="transition_work_to_cinema",
            category=AutomationCategory.INTERRUPTION,
            name="Work → Cinema transition",
            description="Transitions room state from Work Mode (PC music) to Cinema Mode (Fire TV + Projector).",
            required_capabilities=["audio_switch_to_fire_tv", "projector_switch_hdmi1", "media_direct_provider"],
            steps=["fade_pc_music", "wake_fire_tv", "switch_projector_hdmi1", "transfer_soundbar_to_fire_tv"],
            verification="RoomState.MOVIE_ACTIVE",
            estimated_latency_ms=2400,
            risk_level=RiskLevel.MEDIUM,
            parameters_schema={"content": "string (optional)", "provider": "string (optional)"}
        ))

        self.register(AutomationMetadata(
            automation_id="transition_cinema_to_work",
            category=AutomationCategory.INTERRUPTION,
            name="Cinema → Work transition",
            description="Transitions room state from Cinema Mode to Work Mode.",
            required_capabilities=["media_pause", "audio_switch_to_pc"],
            steps=["pause_fire_tv_media", "disconnect_fire_tv_soundbar", "connect_pc_soundbar"],
            verification="RoomState.PC_AUDIO_ACTIVE or IDLE",
            estimated_latency_ms=2500,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="transition_music_to_cinema",
            category=AutomationCategory.INTERRUPTION,
            name="Music → Cinema transition",
            description="Transitions room from PC Music playback to Fire TV Cinema.",
            required_capabilities=["audio_switch_to_fire_tv", "projector_switch_hdmi1"],
            steps=["pause_pc_player", "transfer_soundbar_to_fire_tv", "switch_projector_hdmi1"],
            verification="RoomState.MOVIE_ACTIVE",
            estimated_latency_ms=2200,
            risk_level=RiskLevel.MEDIUM
        ))

        self.register(AutomationMetadata(
            automation_id="transition_cinema_to_music",
            category=AutomationCategory.INTERRUPTION,
            name="Cinema → Music transition",
            description="Transitions room from Fire TV Cinema back to PC Music.",
            required_capabilities=["media_pause", "audio_switch_to_pc"],
            steps=["pause_fire_tv_media", "transfer_soundbar_to_pc", "resume_pc_music"],
            verification="RoomState.PC_AUDIO_ACTIVE",
            estimated_latency_ms=2700,
            risk_level=RiskLevel.LOW
        ))

        # ======================================================================
        # F. ROOM LIFECYCLE (54–59)
        # ======================================================================
        self.register(AutomationMetadata(
            automation_id="arriving_home",
            category=AutomationCategory.LIFECYCLE,
            name="Arriving Home",
            description="Prepares smart room upon arrival: connects soundbar to PC, performs connectivity health checks.",
            required_capabilities=["audio_switch_to_pc", "connectivity_check"],
            steps=["check_connectivity", "connect_pc_soundbar"],
            verification="Soundbar connected to PC AND devices online",
            estimated_latency_ms=3000,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="leaving_home",
            category=AutomationCategory.LIFECYCLE,
            name="Leaving Home",
            description="Shuts down all entertainment, powers down projector, disconnects audio, and puts devices to sleep.",
            required_capabilities=["power_sleep", "audio_switch_to_pc"],
            steps=["stop_all_playback", "disconnect_soundbar", "sleep_fire_tv", "safe_projector_shutdown"],
            verification="all entertainment offline",
            estimated_latency_ms=3500,
            risk_level=RiskLevel.MEDIUM
        ))

        self.register(AutomationMetadata(
            automation_id="goodnight",
            category=AutomationCategory.LIFECYCLE,
            name="Goodnight",
            description="Complete safe bedtime entertainment shutdown: stops all media, sleeps Fire TV, powers off projector, disconnects audio.",
            required_capabilities=["power_sleep", "media_stop"],
            steps=["stop_media", "disconnect_soundbar", "sleep_fire_tv", "safe_projector_shutdown"],
            verification="entertainment fully stopped AND projector OFF AND Fire TV asleep",
            estimated_latency_ms=3500,
            risk_level=RiskLevel.MEDIUM
        ))

        self.register(AutomationMetadata(
            automation_id="morning_entertainment",
            category=AutomationCategory.LIFECYCLE,
            name="Morning Entertainment",
            description="Wakes room for morning entertainment: wakes Fire TV, connects soundbar, opens YouTube morning playlist or news.",
            required_capabilities=["power_wake", "audio_switch_to_fire_tv", "app_launch_youtube"],
            steps=["wake_fire_tv", "transfer_soundbar_to_fire_tv", "launch_youtube_app"],
            verification="Fire TV awake AND A2DP connected AND YouTube foreground",
            estimated_latency_ms=2000,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="entertainment_shutdown",
            category=AutomationCategory.LIFECYCLE,
            name="Entertainment Shutdown",
            description="Graceful full entertainment shutdown without room power down.",
            required_capabilities=["media_stop", "audio_switch_to_pc"],
            steps=["stop_media", "disconnect_fire_tv_soundbar", "restore_pc_audio"],
            verification="entertainment stopped AND audio on PC",
            estimated_latency_ms=2000,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="sync_entertainment_state",
            category=AutomationCategory.LIFECYCLE,
            name="Full Room State Synchronization",
            description="Authoritatively queries fresh physical telemetry from Fire TV, Projector, and PC audio.",
            required_capabilities=["connectivity_check", "bt_get_status"],
            steps=["query_fire_tv_telemetry", "query_projector_telemetry", "query_pc_audio_telemetry"],
            verification="VisualBrainState synchronized with physical truth",
            estimated_latency_ms=300,
            risk_level=RiskLevel.LOW
        ))

        # ======================================================================
        # G. RECOVERY / SELF HEALING (60–67)
        # ======================================================================
        self.register(AutomationMetadata(
            automation_id="recover_fire_tv_adb",
            category=AutomationCategory.RECOVERY,
            name="Recover Fire TV ADB",
            description="Self-heals dropped ADB TCP connection to Fire TV Stick at 192.168.1.5:5555.",
            required_capabilities=["connectivity_check"],
            steps=["reconnect_adb_target"],
            verification="ADB device status: 'device'",
            estimated_latency_ms=1000,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="recover_bluetooth",
            category=AutomationCategory.RECOVERY,
            name="Recover Bluetooth",
            description="Self-heals dropped Fire TV Bluetooth link using direct broadcast and fallback hierarchy.",
            required_capabilities=["bt_connect_soundbar_direct", "bt_connect_soundbar"],
            steps=["retry_direct_connect_broadcast", "fallback_to_settings_navigation"],
            verification="A2DP connected (54:15:89:DC:A5:79)",
            estimated_latency_ms=2500,
            risk_level=RiskLevel.MEDIUM
        ))

        self.register(AutomationMetadata(
            automation_id="recover_soundbar_connection",
            category=AutomationCategory.RECOVERY,
            name="Recover Soundbar Connection",
            description="Resolves cross-host Bluetooth lockup by clearing audio links on both PC and Fire TV.",
            required_capabilities=["audio_switch_to_pc", "audio_switch_to_fire_tv"],
            steps=["force_disconnect_all", "reconnect_designated_host"],
            verification="designated host connected",
            estimated_latency_ms=3500,
            risk_level=RiskLevel.MEDIUM
        ))

        self.register(AutomationMetadata(
            automation_id="recover_projector_hdmi",
            category=AutomationCategory.RECOVERY,
            name="Recover Projector HDMI",
            description="Re-establishes HDMI 1 handshake with projector if input source drifted or blanked.",
            required_capabilities=["projector_switch_hdmi1"],
            steps=["reconnect_projector_adb", "force_hdmi1_source"],
            verification="projector input HDMI 1",
            estimated_latency_ms=1000,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="recover_stuck_streaming_app",
            category=AutomationCategory.RECOVERY,
            name="Recover Stuck Streaming App",
            description="Force-stops frozen foreground streaming application and clears stale task stack.",
            required_capabilities=["app_get_foreground", "navigation_home"],
            steps=["force_stop_foreground_app", "send_nav_home"],
            verification="home screen foreground",
            estimated_latency_ms=800,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="recover_stopped_playback",
            category=AutomationCategory.RECOVERY,
            name="Recover Stopped Playback",
            description="Recovers unexpectedly halted playback by reasserting media focus and issuing play.",
            required_capabilities=["media_play"],
            steps=["reassert_audio_focus", "send_media_play"],
            verification="playback state PLAYING",
            estimated_latency_ms=300,
            risk_level=RiskLevel.LOW
        ))

        self.register(AutomationMetadata(
            automation_id="recover_audio_ownership",
            category=AutomationCategory.RECOVERY,
            name="Recover Audio Ownership",
            description="Arbitrates conflicting audio ownership between PC mpv and Fire TV.",
            required_capabilities=["audio_switch_to_fire_tv", "audio_switch_to_pc"],
            steps=["inspect_current_state", "enforce_authoritative_owner"],
            verification="single authoritative audio owner established",
            estimated_latency_ms=2000,
            risk_level=RiskLevel.LOW,
            parameters_schema={"owner": "string (optional: 'FIRE_TV' | 'PC')"}
        ))

        self.register(AutomationMetadata(
            automation_id="full_entertainment_recovery",
            category=AutomationCategory.RECOVERY,
            name="Full Entertainment Recovery",
            description="Comprehensive sequential recovery of Fire TV ADB, Projector HDMI 1, Bluetooth A2DP, and media session.",
            required_capabilities=["connectivity_check", "projector_switch_hdmi1", "bt_connect_soundbar_direct"],
            steps=["recover_adb", "recover_hdmi", "recover_bluetooth", "recover_media_session"],
            verification="all subsystems green and verified",
            estimated_latency_ms=4500,
            risk_level=RiskLevel.HIGH
        ))
