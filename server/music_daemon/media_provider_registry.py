"""
Media Provider Registry for Animus Smart Room Fire TV Subsystem.
Defines authoritative streaming application profiles, launch components,
supported URI schemes, and capability classifications strictly backed
by empirical device audit.

Invariant:
THE BRAIN UNDERSTANDS.
THE ROUTER DECIDES.
THE SERVICE LAYER ORCHESTRATES.
THE CAPABILITY LAYER EXECUTES.
THE PHYSICAL DEVICES VERIFY.
THE UI REPORTS REALITY.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Dict, Any, List, Tuple

logger = logging.getLogger("music_daemon.media_provider_registry")


class ProviderCapabilityStatus(str, Enum):
    DIRECT_AUTOPLAY_VERIFIED = "DIRECT_AUTOPLAY_VERIFIED"
    DIRECT_PLAY_VERIFIED = "DIRECT_PLAY_VERIFIED"
    DIRECT_LAUNCH_VERIFIED = "DIRECT_LAUNCH_VERIFIED"
    DIRECT_CONTENT_PAGE_VERIFIED = "DIRECT_CONTENT_PAGE_VERIFIED"
    DETAILS_PAGE_ONLY = "DETAILS_PAGE_ONLY"
    APP_LAUNCH_ONLY = "APP_LAUNCH_ONLY"
    SEARCH_FALLBACK = "SEARCH_FALLBACK"
    UI_FALLBACK_REQUIRED = "UI_FALLBACK_REQUIRED"
    UNKNOWN = "UNKNOWN"
    UNVERIFIED = "UNVERIFIED"


@dataclass
class StreamingProvider:
    provider_id: str
    display_name: str
    package_name: str
    launch_component: Optional[str]
    supported_schemes: List[str]
    capability_status: ProviderCapabilityStatus
    autoplay_verified: bool
    uri_templates: Dict[str, str] = field(default_factory=dict)
    description: str = ""

    @property
    def package(self) -> str:
        return self.package_name

    @property
    def component(self) -> Optional[str]:
        return self.launch_component

    @property
    def supports_direct_content(self) -> bool:
        return len(self.uri_templates) > 0 or len(self.supported_schemes) > 0

    @property
    def supports_direct_autoplay(self) -> bool:
        return self.autoplay_verified

    @property
    def supports_content_page(self) -> bool:
        return True

    @property
    def requires_ui_confirmation(self) -> bool:
        return not self.autoplay_verified

    @property
    def verification_strategy(self) -> str:
        if self.autoplay_verified:
            return "PLAYBACK_STATE"
        return "FOREGROUND_PACKAGE"

    def launch_uri(self, content_id_or_url: str, content_type: str = "video") -> Tuple[str, Optional[str]]:
        return self.build_uri(content_id_or_url, content_type=content_type)

    def build_uri(self, content_id_or_url: str, content_type: str = "video") -> Tuple[str, Optional[str]]:
        """
        Builds the authoritative URI and component for this provider.
        Returns (uri: str, component: Optional[str]).
        """
        raw = (content_id_or_url or "").strip()
        if not raw:
            return "", self.launch_component

        # If it's already a full URI matching supported schemes, return directly
        if any(raw.startswith(scheme + "://") or raw.startswith(scheme + ":") for scheme in self.supported_schemes):
            return raw, self.launch_component

        # Use template if available
        if content_type in self.uri_templates:
            template = self.uri_templates[content_type]
            return template.format(id=raw), self.launch_component

        # Fallback to first available template if content_type not found
        if self.uri_templates:
            first_template = next(iter(self.uri_templates.values()))
            return first_template.format(id=raw), self.launch_component

        # Fallback to direct string if valid
        return raw, self.launch_component


# Provider-independent interface alias
StreamingProviderCapability = StreamingProvider


class MediaProviderRegistry:
    """
    Registry of streaming media providers installed on the Fire TV Stick.
    Populated strictly from forensic audit evidence.
    """

    def __init__(self):
        self._providers: Dict[str, StreamingProvider] = {}
        self._init_default_providers()

    def _init_default_providers(self):
        # 1. YouTube TV (Cobalt) — Fully Autoplay Verified
        self.register(StreamingProvider(
            provider_id="youtube",
            display_name="YouTube",
            package_name="com.amazon.firetv.youtube",
            launch_component="com.amazon.firetv.youtube/dev.cobalt.app.MainActivity",
            supported_schemes=["https", "http", "youtube", "vnd.youtube"],
            capability_status=ProviderCapabilityStatus.DIRECT_AUTOPLAY_VERIFIED,
            autoplay_verified=True,
            uri_templates={
                "video": "https://www.youtube.com/watch?v={id}",
                "watch": "https://www.youtube.com/watch?v={id}",
                "custom": "vnd.youtube:{id}"
            },
            description="YouTube TV Leanback. Accepts direct video IDs and URLs with ~162ms instant playback."
        ))

        # 2. JioHotstar (Disney+ Hotstar) — Direct Autoplay / Launch Verified
        self.register(StreamingProvider(
            provider_id="hotstar",
            display_name="JioHotstar",
            package_name="in.startv.hotstar",
            launch_component="in.startv.hotstar/com.hotstar.MainActivity",
            supported_schemes=["https", "http", "hotstar"],
            capability_status=ProviderCapabilityStatus.DIRECT_AUTOPLAY_VERIFIED,
            autoplay_verified=True,
            uri_templates={
                "movie": "https://www.hotstar.com/movies/{id}",
                "tv": "https://www.hotstar.com/tv/{id}",
                "content": "https://www.hotstar.com/in/{id}"
            },
            description="JioHotstar TV. Opens content and autoplays directly."
        ))

        # 3. Netflix — Direct Content Page Launch Verified (Autoplay NOT yet authoritative)
        self.register(StreamingProvider(
            provider_id="netflix",
            display_name="Netflix",
            package_name="com.netflix.ninja",
            launch_component="com.netflix.ninja/.MainActivity",
            supported_schemes=["https", "http", "netflix"],
            capability_status=ProviderCapabilityStatus.DIRECT_LAUNCH_VERIFIED,
            autoplay_verified=False,
            uri_templates={
                "watch": "https://www.netflix.com/watch/{id}",
                "title": "https://www.netflix.com/title/{id}"
            },
            description="Netflix TV Ninja. Deep links directly to watch/title IDs in ~216ms (shows title page)."
        ))

        # 4. Zee5 — Direct Content Page Launch Verified
        self.register(StreamingProvider(
            provider_id="zee5",
            display_name="Zee5",
            package_name="com.zee5.amazon",
            launch_component="com.zee5.amazon/com.zee5.android.launch.presentation.AppStartActivity",
            supported_schemes=["https", "http", "zee5"],
            capability_status=ProviderCapabilityStatus.DIRECT_LAUNCH_VERIFIED,
            autoplay_verified=False,
            uri_templates={
                "movie": "https://www.zee5.com/movies/details/{id}",
                "details": "https://www.zee5.com/{id}"
            },
            description="Zee5 Fire TV app. Opens movie details and content links in ~138ms."
        ))

        # 5. Apple TV — Direct Content Page Launch Verified
        self.register(StreamingProvider(
            provider_id="apple_tv",
            display_name="Apple TV",
            package_name="com.apple.atve.amazon.appletv",
            launch_component="com.apple.atve.amazon.appletv/.MainActivity",
            supported_schemes=["https", "http"],
            capability_status=ProviderCapabilityStatus.DIRECT_LAUNCH_VERIFIED,
            autoplay_verified=False,
            uri_templates={
                "title": "https://tv.apple.com/in/{id}"
            },
            description="Apple TV Fire TV application. Deep links to content page in ~212ms."
        ))

        # 6. Prime Video — Direct Content Page Launch Verified
        self.register(StreamingProvider(
            provider_id="prime_video",
            display_name="Prime Video",
            package_name="com.amazon.cloud9",
            launch_component="com.amazon.cloud9/com.amazon.slate.fire_tv.FireTvSlateActivity",
            supported_schemes=["https", "http", "amzn"],
            capability_status=ProviderCapabilityStatus.DETAILS_PAGE_ONLY,
            autoplay_verified=False,
            uri_templates={
                "detail": "https://www.amazon.com/gp/video/detail/{id}",
                "asin": "https://www.amazon.com/gp/video/detail/{id}"
            },
            description="Prime Video Fire TV Slate detail page in ~114ms."
        ))

        # 7. Airtel Xstream Play — Direct Launch Verified
        self.register(StreamingProvider(
            provider_id="airtel_xstream",
            display_name="Airtel Xstream",
            package_name="tv.airtel.xstream.tvapp",
            launch_component="tv.airtel.xstream.tvapp/tv.airtel.xstream.splash.SplashActivity",
            supported_schemes=["xstream", "wynkpremiere", "tvrecommendation", "https"],
            capability_status=ProviderCapabilityStatus.DIRECT_LAUNCH_VERIFIED,
            autoplay_verified=False,
            uri_templates={
                "content": "xstream://xstreamplay.com/{id}"
            },
            description="Airtel Xstream TV app with custom xstream:// scheme."
        ))

        # 8. SonyLIV — Details Page Only / Installed
        self.register(StreamingProvider(
            provider_id="sonyliv",
            display_name="SonyLIV",
            package_name="com.onemainstream.sonyliv.android",
            launch_component="com.onemainstream.sonyliv.android/com.sonyliv.ui.splash.SplashActivity",
            supported_schemes=["sonyliv", "sony", "https", "http"],
            capability_status=ProviderCapabilityStatus.DETAILS_PAGE_ONLY,
            autoplay_verified=False,
            uri_templates={
                "movie": "https://www.sonyliv.com/movies/{id}"
            },
            description="SonyLIV TV app."
        ))

        # 9. Discovery+ — Details Page Only / Installed
        self.register(StreamingProvider(
            provider_id="discovery_plus",
            display_name="Discovery+",
            package_name="com.discoveryplus.tv.fire",
            launch_component="com.discoveryplus.tv.fire/.DPlusFireTvActivity",
            supported_schemes=["discoveryplus"],
            capability_status=ProviderCapabilityStatus.DETAILS_PAGE_ONLY,
            autoplay_verified=False,
            uri_templates={
                "show": "discoveryplus://show/{id}"
            },
            description="Discovery+ Fire TV app."
        ))

        # 10. Hoichoi — Details Page Only / Installed
        self.register(StreamingProvider(
            provider_id="hoichoi",
            display_name="Hoichoi",
            package_name="com.viewlift.hoichoiprod",
            launch_component="com.viewlift.hoichoiprod/com.viewlift.hoichoi.ui.DeeplinkActivity",
            supported_schemes=["https", "http", "hoichoi.tv"],
            capability_status=ProviderCapabilityStatus.DETAILS_PAGE_ONLY,
            autoplay_verified=False,
            uri_templates={
                "title": "https://www.hoichoi.tv/{id}"
            },
            description="Hoichoi Bengali Streaming app."
        ))

        # 11. MX Player — Details Page Only / Installed
        self.register(StreamingProvider(
            provider_id="mx_player",
            display_name="MX Player",
            package_name="com.mxtech.videoplayer.television",
            launch_component="com.mxtech.videoplayer.television/com.mxtech.videoplayer.tv.core.DeepLinkActivity",
            supported_schemes=["mxtv", "mxplay", "https", "http"],
            capability_status=ProviderCapabilityStatus.DETAILS_PAGE_ONLY,
            autoplay_verified=False,
            uri_templates={
                "watch": "https://www.mxplayer.in/movie/{id}"
            },
            description="MX Player TV application."
        ))

    def register(self, provider: StreamingProvider):
        self._providers[provider.provider_id.lower()] = provider

    def get_provider(self, provider_id: str) -> Optional[StreamingProvider]:
        if not provider_id:
            return None
        return self._providers.get(provider_id.strip().lower())

    def get_provider_for_package(self, package_name: str) -> Optional[StreamingProvider]:
        if not package_name:
            return None
        for p in self._providers.values():
            if p.package_name.lower() == package_name.strip().lower():
                return p
        return None

    def get_provider_for_url(self, url: str) -> Optional[StreamingProvider]:
        if not url:
            return None
        u = url.lower()
        if "youtube.com" in u or "youtu.be" in u or u.startswith("vnd.youtube"):
            return self._providers.get("youtube")
        if "hotstar.com" in u:
            return self._providers.get("hotstar")
        if "netflix.com" in u:
            return self._providers.get("netflix")
        if "zee5.com" in u:
            return self._providers.get("zee5")
        if "tv.apple.com" in u:
            return self._providers.get("apple_tv")
        if "amazon.com/gp/video" in u or "primevideo.com" in u:
            return self._providers.get("prime_video")
        if "xstreamplay.com" in u or u.startswith("xstream://"):
            return self._providers.get("airtel_xstream")
        if "sonyliv.com" in u:
            return self._providers.get("sonyliv")
        if "hoichoi.tv" in u:
            return self._providers.get("hoichoi")
        if "mxplayer.in" in u or "mxplay.com" in u:
            return self._providers.get("mx_player")
        return None

    def list_providers(self) -> List[StreamingProvider]:
        return list(self._providers.values())

    def resolve_launch_intent(self, provider_id: str, content_id_or_url: str) -> Tuple[bool, str, Optional[str], str]:
        """
        Resolves the intent action, URI, and component.
        Returns (success: bool, uri: str, component: Optional[str], status_msg: str).
        """
        provider = self.get_provider(provider_id)
        if not provider:
            return False, "", None, f"Unknown streaming provider '{provider_id}'"

        uri, component = provider.build_uri(content_id_or_url)
        return True, uri, component, f"Resolved {provider.display_name} intent"

    def evaluate_truthful_status(
        self,
        provider_id: str,
        foreground_matched: bool,
        media_session_playing: bool
    ) -> str:
        """
        Evaluates truthful status based on provider capability status and physical telemetry.
        """
        provider = self.get_provider(provider_id)
        if not foreground_matched:
            return "app launch failed"
        if not provider:
            return "provider foreground active"
        if provider.autoplay_verified or media_session_playing:
            return "movie playing"
        return "content page opened"

    def get_registry_dict(self) -> Dict[str, Any]:
        """
        Returns JSON-serializable dictionary of provider capabilities.
        """
        return {
            pid: {
                "display_name": p.display_name,
                "package_name": p.package_name,
                "launch_component": p.launch_component,
                "capability_status": p.capability_status.value,
                "autoplay_verified": p.autoplay_verified,
                "supported_schemes": p.supported_schemes,
                "supports_direct_content": p.supports_direct_content,
                "supports_direct_autoplay": p.supports_direct_autoplay,
                "requires_ui_confirmation": p.requires_ui_confirmation,
                "verification_strategy": p.verification_strategy,
                "description": p.description
            }
            for pid, p in self._providers.items()
        }
