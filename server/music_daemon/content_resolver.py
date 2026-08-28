"""
Smart Room Content Resolution Layer for Animus Fire TV Subsystem.
Decouples high-level user requests and natural language titles from device-specific
launch mechanisms by resolving titles into explicit providers, content IDs,
and direct playback URIs.

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
import re
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Tuple

from media_provider_registry import MediaProviderRegistry, StreamingProvider

logger = logging.getLogger("music_daemon.content_resolver")

# Regex for YouTube Video ID: 11 characters base64url
YOUTUBE_VIDEO_ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]{11}$")
# Regex for YouTube URL extraction
YOUTUBE_URL_REGEX = re.compile(r"(?:https?://)?(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([a-zA-Z0-9_-]{11})")
# Regex for explicit video ID spoken phrases e.g. "video id 07d2dXHYb94" or "video 07d2dXHYb94"
SPOKEN_VIDEO_ID_REGEX = re.compile(r"(?:video\s+id\s+|id\s+)([a-zA-Z0-9_-]{11})", re.IGNORECASE)


@dataclass
class ResolvedContent:
    provider_id: str
    raw_query: str
    title: str
    content_id: Optional[str]
    direct_uri: Optional[str]
    launch_component: Optional[str]
    resolution_type: str  # "DIRECT_VIDEO_ID" | "DIRECT_URI" | "PROVIDER_DETAILS" | "SEARCH_QUERY"
    confidence: str  # "HIGH" | "MEDIUM" | "LOW"
    provider_display_name: str = ""
    autoplay_supported: bool = False
    details: Dict[str, Any] = field(default_factory=dict)

    @property
    def resolved_id(self) -> Optional[str]:
        return self.content_id

    @property
    def content_query(self) -> str:
        return self.title or self.raw_query


# Backward & cross-module compatibility alias
ContentResolutionResult = ResolvedContent


class SmartRoomContentResolver:
    """
    Authoritative content resolver for smart room media workflows.
    Resolves spoken or typed content queries into structured streaming intents.
    """

    def __init__(self, music_resolver=None, provider_registry: Optional[MediaProviderRegistry] = None, watchmode_resolver=None):
        self.music_resolver = music_resolver
        self.provider_registry = provider_registry or MediaProviderRegistry()
        if watchmode_resolver is not None:
            self.watchmode = watchmode_resolver
        else:
            try:
                from watchmode_resolver import WatchmodeResolver
                self.watchmode = WatchmodeResolver()
            except Exception:
                self.watchmode = None

    def _extract_provider_from_text(self, text: str) -> Tuple[str, Optional[str]]:
        """
        Parses text for provider mentions like 'on hotstar', 'on netflix', 'on youtube', 'on zee5',
        or leading intents like 'watch netflix', 'open prime video', 'youtube article 15'.
        Returns (cleaned_title, provider_id_or_None).
        """
        clean_text = text.strip()
        lower = clean_text.lower()

        # Leading provider prefixes e.g. "youtube article 15", "netflix stranger things", "prime mirzapur"
        prefix_map = [
            (r"^youtube\s+", "youtube"),
            (r"^yt\s+", "youtube"),
            (r"^netflix\s+", "netflix"),
            (r"^hotstar\s+", "hotstar"),
            (r"^jio\s*hotstar\s+", "hotstar"),
            (r"^prime\s+video\s+", "prime_video"),
            (r"^prime\s+", "prime_video"),
            (r"^apple\s*tv\s+", "apple_tv"),
            (r"^zee5\s+", "zee5"),
            (r"^sonyliv\s+", "sonyliv"),
            (r"^airtel\s*xstream\s+", "airtel_xstream"),
            (r"^mx\s*player\s+", "mx_player"),
            (r"^hoichoi\s+", "hoichoi"),
        ]

        # Strip standard conversational prefixes and temporal markers:
        # "buddy play...", "please open...", "put on...", "let's watch...", "I feel like watching..."
        clean_text = re.sub(
            r"\s+(?:right\s+now|now|at\s+the\s+moment|tonight|today)\s*$",
            "",
            clean_text,
            flags=re.IGNORECASE
        ).strip()

        clean_text = re.sub(
            r"^(?:buddy|hey\s+buddy|alexa|computer|please|can\s+you|could\s+you|let['’]s|i\s+(?:want|would\s+like|feel\s+like|am\s+in\s+the\s+mood)\s+(?:to\s+)?)\s*",
            "",
            clean_text,
            flags=re.IGNORECASE
        ).strip()

        action_match = re.match(
            r"^(?:watching|watch|see|put\s+on|launch|open|start|play)\s+(?:the\s+movie\s+|movie\s+|the\s+film\s+|film\s+|the\s+)?(.+)$",
            clean_text,
            flags=re.IGNORECASE
        )
        if action_match:
            clean_text = action_match.group(1).strip()

        lower = clean_text.lower()

        # Check pure app launch phrases e.g. "open netflix", "launch prime video", "open youtube"
        direct_apps = {
            "netflix": ["netflix"],
            "youtube": ["youtube", "yt"],
            "hotstar": ["hotstar", "disney hotstar", "disney+ hotstar", "jiohotstar", "jio hotstar"],
            "prime_video": ["prime video", "prime", "amazon prime", "amazon prime video"],
            "apple_tv": ["apple tv", "apple tv plus", "appletv", "apple tv+"],
            "zee5": ["zee5", "zee 5"],
            "sonyliv": ["sonyliv", "sony liv"],
            "airtel_xstream": ["airtel xstream", "xstream", "airtel xstream play"],
            "discovery_plus": ["discovery plus", "discovery+"],
            "hoichoi": ["hoichoi"],
            "mx_player": ["mx player", "mxplayer"],
        }

        # Check if query is just "watch <app>", "open <app>", "put on <app>", or pure "<app>"
        for pid, aliases in direct_apps.items():
            for alias in aliases:
                exact_commands = [
                    f"watch {alias}", f"play {alias}", f"open {alias}", f"launch {alias}",
                    f"start {alias}", f"put on {alias}", f"put {alias}",
                    f"put {alias} on the projector", f"put {alias} on the tv", f"put {alias} on tv",
                    f"switch to {alias}", f"switch {alias}", alias
                ]
                if lower in exact_commands:
                    return "", pid

        # Trailing provider patterns e.g. "Article 15 on Hotstar", "Stranger Things on Netflix"
        provider_patterns = [
            (r"\s+on\s+youtube\s*$", "youtube"),
            (r"\s+on\s+hotstar\s*$", "hotstar"),
            (r"\s+on\s+disney\+?\s*hotstar\s*$", "hotstar"),
            (r"\s+on\s+jio\s*hotstar\s*$", "hotstar"),
            (r"\s+on\s+netflix\s*$", "netflix"),
            (r"\s+on\s+zee5\s*$", "zee5"),
            (r"\s+on\s+apple\s*tv\s*$", "apple_tv"),
            (r"\s+on\s+airtel\s*xstream\s*$", "airtel_xstream"),
            (r"\s+on\s+sonyliv\s*$", "sonyliv"),
            (r"\s+on\s+prime\s*video\s*$", "prime_video"),
            (r"\s+on\s+prime\s*$", "prime_video"),
            (r"\s+on\s+mx\s*player\s*$", "mx_player"),
            (r"\s+on\s+hoichoi\s*$", "hoichoi"),
        ]

        detected_pid = None
        for pattern, pid in provider_patterns:
            m = re.search(pattern, lower)
            if m:
                clean_text = clean_text[:m.start()].strip()
                lower = clean_text.lower()
                detected_pid = pid
                break

        # Leading provider prefixes e.g. "YouTube Article 15"
        if not detected_pid:
            for pat, pid in prefix_map:
                m = re.match(pat, lower)
                if m:
                    clean_text = clean_text[m.end():].strip()
                    lower = clean_text.lower()
                    detected_pid = pid
                    break

        # Strip leading action verbs: "watch", "play", "put on", "put", "stream", "show me", "open"
        clean_text = re.sub(
            r"^(?:i\s+want\s+to\s+watch|i\s+wanna\s+watch|please\s+watch|watch|please\s+play|play|open|launch|start|stream|put\s+on|put|show\s+me)\s+",
            "",
            clean_text,
            flags=re.IGNORECASE
        ).strip()

        # Handle "put <title> on the projector / tv / screen"
        m_put = re.match(r"^(.+?)\s+on\s+(?:the\s+)?(?:tv|projector|screen)$", clean_text, re.IGNORECASE)
        if m_put:
            clean_text = m_put.group(1).strip()

        return clean_text, detected_pid

    def resolve(self, query: str, explicit_provider: Optional[str] = None) -> ResolvedContent:
        """Alias for resolve_content to satisfy Phase E.2 interface."""
        return self.resolve_content(query, explicit_provider=explicit_provider)

    def resolve_content(self, query: str, explicit_provider: Optional[str] = None) -> ResolvedContent:
        """
        Resolves content query into a structured ResolvedContent contract.
        Follows strict resolution hierarchy:
        1. Explicit video/content ID
        2. Explicit URL
        3. Spoken video ID extraction
        4. Target provider extraction
        5. Catalog resolver lookup (YTM / YT catalog)
        6. Provider details deep link or UI search fallback
        """
        if not query or not query.strip():
            target_p = explicit_provider or "youtube"
            provider = self.provider_registry.get_provider(target_p) or self.provider_registry.get_provider("youtube")
            return ResolvedContent(
                provider_id=provider.provider_id,
                raw_query="",
                title="",
                content_id=None,
                direct_uri=None,
                launch_component=provider.launch_component,
                resolution_type="APP_LAUNCH_ONLY" if explicit_provider else "SEARCH_QUERY",
                confidence="HIGH" if explicit_provider else "LOW",
                provider_display_name=provider.display_name,
                autoplay_supported=provider.autoplay_verified,
                details={"reason": "Explicit provider launch" if explicit_provider else "Empty query"}
            )

        raw = query.strip()
        logger.info(f"[CONTENT_RESOLVER] Resolving content query='{raw}', explicit_provider='{explicit_provider}'")

        # 1. Direct URL check
        if raw.startswith("http://") or raw.startswith("https://") or "://" in raw:
            provider = self.provider_registry.get_provider_for_url(raw)
            if provider:
                yt_m = YOUTUBE_URL_REGEX.search(raw)
                vid = yt_m.group(1) if yt_m else None
                return ResolvedContent(
                    provider_id=provider.provider_id,
                    raw_query=raw,
                    title=raw,
                    content_id=vid,
                    direct_uri=raw,
                    launch_component=provider.launch_component,
                    resolution_type="DIRECT_VIDEO_ID" if vid else "DIRECT_URI",
                    confidence="HIGH",
                    provider_display_name=provider.display_name,
                    autoplay_supported=provider.autoplay_verified,
                    details={"source": "direct_url"}
                )

        # 2. Raw YouTube Video ID check (exact 11 chars)
        if YOUTUBE_VIDEO_ID_REGEX.match(raw):
            yt_provider = self.provider_registry.get_provider("youtube")
            watch_url, component = yt_provider.build_uri(raw, "video")
            return ResolvedContent(
                provider_id="youtube",
                raw_query=raw,
                title=raw,
                content_id=raw,
                direct_uri=watch_url,
                launch_component=component,
                resolution_type="DIRECT_VIDEO_ID",
                confidence="HIGH",
                provider_display_name="YouTube",
                autoplay_supported=True,
                details={"source": "raw_video_id"}
            )

        # 3. Spoken Video ID check (e.g. "play video id 07d2dXHYb94" or "video ID 07d2dXHYb94 on YouTube")
        spoken_m = SPOKEN_VIDEO_ID_REGEX.search(raw)
        if spoken_m:
            vid = spoken_m.group(1)
            yt_provider = self.provider_registry.get_provider("youtube")
            watch_url, component = yt_provider.build_uri(vid, "video")
            return ResolvedContent(
                provider_id="youtube",
                raw_query=raw,
                title=raw,
                content_id=vid,
                direct_uri=watch_url,
                launch_component=component,
                resolution_type="DIRECT_VIDEO_ID",
                confidence="HIGH",
                provider_display_name="YouTube",
                autoplay_supported=True,
                details={"source": "spoken_video_id", "extracted_id": vid}
            )

        # 4. Extract provider from spoken query if not explicit
        cleaned_title, detected_provider = self._extract_provider_from_text(raw)
        provider_id = (explicit_provider or detected_provider or "youtube").strip().lower()
        provider = self.provider_registry.get_provider(provider_id) or self.provider_registry.get_provider("youtube")

        # If query resolved to pure app launch (no title or generic placeholder like 'something')
        if not cleaned_title or cleaned_title.lower() in ("something", "anything", "stuff", "videos", "movies", "shows", "video", "movie", "show"):
            return ResolvedContent(
                provider_id=provider.provider_id,
                raw_query=raw,
                title="",
                content_id=None,
                direct_uri=None,
                launch_component=provider.launch_component,
                resolution_type="APP_LAUNCH_ONLY",
                confidence="HIGH",
                provider_display_name=provider.display_name,
                autoplay_supported=False,
                details={"app_launch": True, "provider_detected": bool(detected_provider)}
            )

        # 5. Non-YouTube providers: check Watchmode for exact deep-link / numeric content ID
        if provider.provider_id != "youtube":
            resolved_content_id = cleaned_title
            resolved_uri = None
            if getattr(self, "watchmode", None):
                try:
                    ott_info = self.watchmode.resolve_title(cleaned_title, target_provider=provider.provider_id)
                    if ott_info and (ott_info.get("content_id") or ott_info.get("web_url")):
                        resolved_content_id = str(ott_info.get("content_id") or cleaned_title)
                        resolved_uri = ott_info.get("web_url")
                except Exception as e:
                    logger.warning(f"[CONTENT_RESOLVER_WATCHMODE_ERROR] {e}")

            if not resolved_uri:
                resolved_uri, component = provider.build_uri(resolved_content_id, "content")
            else:
                component = provider.launch_component

            is_direct_id = bool(getattr(self, "watchmode", None) and resolved_content_id != cleaned_title)
            return ResolvedContent(
                provider_id=provider.provider_id,
                raw_query=raw,
                title=cleaned_title,
                content_id=resolved_content_id,
                direct_uri=resolved_uri,
                launch_component=component,
                resolution_type="PROVIDER_DETAILS",
                confidence="HIGH" if is_direct_id else "MEDIUM",
                provider_display_name=provider.display_name,
                autoplay_supported=provider.autoplay_verified,
                details={"provider_detected": bool(detected_provider), "explicit": bool(explicit_provider), "watchmode_resolved": is_direct_id}
            )

        # 6. YouTube resolution: attempt catalog resolution to extract Video ID for instant autoplay
        if self.music_resolver:
            try:
                # Use catalog search via YTMusic/yt-dlp
                if hasattr(self.music_resolver, "ytm") and self.music_resolver.ytm:
                    search_res = self.music_resolver._execute_with_ytm(
                        lambda client: client.search(cleaned_title, filter="videos", limit=3) or client.search(cleaned_title, limit=3)
                    )
                    if search_res and isinstance(search_res, list) and len(search_res) > 0:
                        top = search_res[0]
                        vid = top.get("videoId")
                        if vid:
                            res_title = top.get("title", cleaned_title)
                            watch_url, component = provider.build_uri(vid, "video")
                            logger.info(f"[CONTENT_RESOLVER_HIT] Resolved '{cleaned_title}' -> YouTube videoId={vid} ('{res_title}')")
                            return ResolvedContent(
                                provider_id="youtube",
                                raw_query=raw,
                                title=res_title,
                                content_id=vid,
                                direct_uri=watch_url,
                                launch_component=component,
                                resolution_type="DIRECT_VIDEO_ID",
                                confidence="HIGH",
                                provider_display_name="YouTube",
                                autoplay_supported=True,
                                details={"source": "ytmusic_catalog_search", "original_query": cleaned_title}
                            )
            except Exception as e:
                logger.warning(f"[CONTENT_RESOLVER_CATALOG_WARNING] Catalog search error: {e}")

        # 7. Fallback to Search Query for UI typing
        logger.info(f"[CONTENT_RESOLVER_FALLBACK] Could not resolve direct video ID for '{cleaned_title}'. Using UI search fallback.")
        return ResolvedContent(
            provider_id="youtube",
            raw_query=raw,
            title=cleaned_title,
            content_id=None,
            direct_uri=None,
            launch_component=provider.launch_component,
            resolution_type="SEARCH_QUERY",
            confidence="MEDIUM",
            provider_display_name="YouTube",
            autoplay_supported=True,
            details={"fallback": "ui_search_required"}
        )


# Backward & cross-module compatibility alias
ContentResolver = SmartRoomContentResolver
