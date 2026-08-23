"""
Music resolution service using ytmusicapi for structured metadata search
and yt-dlp for direct streaming audio URL extraction.

Supports:
- Authenticated YouTube Music sessions (oauth.json + OAuthCredentials or headers_auth.json or cookies.txt in secrets/)
- Automatic fallback to unauthenticated guest mode if credentials are missing, corrupt, or expired
"""

import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, Tuple, List
from ytmusicapi import YTMusic
from ytmusicapi.auth.oauth.credentials import OAuthCredentials
import yt_dlp

logger = logging.getLogger("music_daemon.resolver")

SECRETS_DIR = Path(__file__).resolve().parent / "secrets"
OAUTH_CLIENT_FILE = SECRETS_DIR / "oauth_client.json"
OAUTH_TOKEN_FILE = SECRETS_DIR / "oauth.json"
HEADERS_AUTH_FILE = SECRETS_DIR / "headers_auth.json"
COOKIES_FILE = SECRETS_DIR / "cookies.txt"


@dataclass
class ResolvedTrack:
    video_id: str
    title: str
    artist: str
    duration: Optional[int]
    stream_url: str
    thumbnail_url: Optional[str] = None
    is_authenticated: bool = False


class MusicResolver:
    """
    Abstract interface for music track resolution.
    """
    def resolve(self, title: str, artist: Optional[str] = None, direct_id: Optional[str] = None) -> Optional[ResolvedTrack]:
        raise NotImplementedError


class YouTubeMusicResolver(MusicResolver):
    """
    Resolves track title/artist via YouTube Music catalog and extracts
    direct audio streaming URL via yt-dlp.
    Supports authenticated sessions with graceful fallback to unauthenticated guest mode.
    """
    def __init__(self, secrets_dir: Optional[Path] = None):
        self.secrets_dir = secrets_dir or SECRETS_DIR
        self.oauth_client_file = self.secrets_dir / "oauth_client.json"
        self.oauth_token_file = self.secrets_dir / "oauth.json"
        self.headers_auth_file = self.secrets_dir / "headers_auth.json"
        self.cookies_file = self.secrets_dir / "cookies.txt"

        self.is_authenticated = False
        self.auth_method = "none"
        self.ytm: Optional[YTMusic] = None

        self._init_clients()

    def _load_client_credentials(self) -> Tuple[Optional[str], Optional[str]]:
        """
        Loads client_id and client_secret from environment or secrets/oauth_client.json.
        """
        client_id = os.environ.get("YTM_CLIENT_ID")
        client_secret = os.environ.get("YTM_CLIENT_SECRET")
        if client_id and client_secret:
            return client_id.strip(), client_secret.strip()

        if self.oauth_client_file.is_file():
            try:
                with open(self.oauth_client_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if "installed" in data:
                        data = data["installed"]
                    elif "web" in data:
                        data = data["web"]
                    cid = data.get("client_id")
                    csec = data.get("client_secret")
                    if cid and csec:
                        return str(cid).strip(), str(csec).strip()
            except Exception as e:
                logger.warning(f"[PC_MUSIC_AUTH] Could not parse client credentials: {e}")

        return None, None

    def _init_clients(self):
        """
        Initializes ytmusicapi and yt-dlp configurations.
        Attempts authenticated session first; falls back to guest mode seamlessly.
        """
        client_id, client_secret = self._load_client_credentials()

        # 1. Attempt OAuth authenticated session
        if self.oauth_token_file.is_file() and client_id and client_secret:
            try:
                oauth_creds = OAuthCredentials(client_id=client_id, client_secret=client_secret)
                self.ytm = YTMusic(auth=str(self.oauth_token_file), oauth_credentials=oauth_creds)
                self.is_authenticated = True
                self.auth_method = "oauth"
                logger.info(f"[PC_MUSIC_AUTH] Authenticated session loaded via OAuth ({self.oauth_token_file.name})")
            except Exception as e:
                logger.warning(f"[PC_MUSIC_AUTH_EXPIRED] Failed to load OAuth session ({e}). Falling back to guest mode.")
                self.is_authenticated = False
                self.auth_method = "none"

        # 2. Attempt headers_auth.json session if not already authenticated
        if not self.is_authenticated and self.headers_auth_file.is_file():
            try:
                self.ytm = YTMusic(str(self.headers_auth_file))
                self.is_authenticated = True
                self.auth_method = "headers_auth"
                logger.info(f"[PC_MUSIC_AUTH] Authenticated session loaded via headers_auth ({self.headers_auth_file.name})")
            except Exception as e:
                logger.warning(f"[PC_MUSIC_AUTH_EXPIRED] Failed to load headers_auth ({e}). Falling back to guest mode.")
                self.is_authenticated = False
                self.auth_method = "none"

        # 3. Fallback to guest mode if no valid auth found
        if not self.is_authenticated:
            try:
                self.ytm = YTMusic()
                logger.info("[PC_MUSIC_RESOLVER_INIT] Initialized in GUEST MODE (unauthenticated).")
            except Exception as e:
                logger.warning(f"[PC_MUSIC_RESOLVER_INIT] Error initializing guest YTMusic client: {e}")
                self.ytm = None

    def _get_ydl_opts(self) -> Dict[str, Any]:
        """
        Builds yt-dlp options including cookies if present in secrets.
        """
        opts: Dict[str, Any] = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'extract_flat': False,
        }
        if self.cookies_file.is_file():
            opts['cookiefile'] = str(self.cookies_file)
            logger.debug(f"[PC_MUSIC_YTDLP] Using cookies file: {self.cookies_file.name}")
        return opts

    def _execute_with_ytm(self, func):
        """
        Executes a YTMusic callable with automatic fallback to unauthenticated guest mode
        if the active OAuth/headers session has expired, corrupt, or returned HTTP 400/401/403.
        """
        if not self.ytm:
            try:
                self.ytm = YTMusic()
            except Exception:
                return None

        try:
            return func(self.ytm)
        except Exception as e:
            logger.warning(f"[PC_MUSIC_AUTH_DEGRADED] Authenticated YTMusic operation failed ({e}). Falling back to fresh guest client.")
            try:
                self.ytm = YTMusic()
                self.is_authenticated = False
                self.auth_method = "none"
                return func(self.ytm)
            except Exception as e2:
                logger.warning(f"[PC_MUSIC_GUEST_FAILED] Guest YTMusic operation failed: {e2}")
                return None

    def get_auth_status(self) -> Dict[str, Any]:
        return {
            "is_authenticated": self.is_authenticated,
            "auth_method": self.auth_method,
            "has_cookies": self.cookies_file.is_file()
        }

    def resolve(self, title: str, artist: Optional[str] = None, direct_id: Optional[str] = None) -> Optional[ResolvedTrack]:
        query = f"{title} {artist}".strip() if artist else title.strip()
        logger.info(f"[PC_MUSIC_RESOLVING] Resolving music for query='{query}', direct_id='{direct_id}' (authenticated={self.is_authenticated})")

        video_id = direct_id
        resolved_title = title
        resolved_artist = artist or "Unknown Artist"
        resolved_duration = None
        thumbnail_url = None

        # 1. Query YouTube Music catalog for exact song metadata
        if not video_id:
            try:
                search_results = self._execute_with_ytm(lambda client: client.search(query, filter="songs", limit=5))
                if search_results and isinstance(search_results, list) and len(search_results) > 0:
                    top_song = search_results[0]
                    video_id = top_song.get("videoId")
                    resolved_title = top_song.get("title", title)
                    artists = top_song.get("artists")
                    if artists and isinstance(artists, list) and len(artists) > 0:
                        resolved_artist = artists[0].get("name", resolved_artist)
                    resolved_duration = top_song.get("duration_seconds")
                    thumbnails = top_song.get("thumbnails")
                    if thumbnails and isinstance(thumbnails, list) and len(thumbnails) > 0:
                        thumbnail_url = thumbnails[-1].get("url")
                    logger.info(f"[PC_MUSIC_SEARCH_HIT] Found song '{resolved_title}' by '{resolved_artist}' (videoId={video_id})")
            except Exception as e:
                logger.warning(f"[PC_MUSIC_SEARCH_WARNING] YTMusic search failed: {e}. Falling back to direct yt-dlp search.")

        # 2. Extract direct audio stream URL via yt-dlp
        ydl_opts = self._get_ydl_opts()
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                target = f"https://music.youtube.com/watch?v={video_id}" if video_id else f"ytsearch1:{query}"
                info = ydl.extract_info(target, download=False)
                if not info:
                    logger.error(f"[PC_MUSIC_RESOLVE_FAILED] yt-dlp could not extract stream for '{query}'")
                    return None

                if "entries" in info and info["entries"]:
                    info = info["entries"][0]

                stream_url = info.get("url")
                if not stream_url:
                    logger.error(f"[PC_MUSIC_RESOLVE_FAILED] No direct audio stream URL found for '{query}'")
                    return None

                if not video_id:
                    video_id = info.get("id", "unknown_id")
                    resolved_title = info.get("title", resolved_title)
                    resolved_artist = info.get("uploader", resolved_artist)
                    resolved_duration = info.get("duration", resolved_duration)
                    thumbnail_url = info.get("thumbnail", thumbnail_url)

                logger.info(f"[PC_MUSIC_RESOLVED] Track resolved: '{resolved_title}' by '{resolved_artist}' ({resolved_duration}s) (auth={self.is_authenticated})")
                return ResolvedTrack(
                    video_id=video_id,
                    title=resolved_title,
                    artist=resolved_artist,
                    duration=resolved_duration,
                    stream_url=stream_url,
                    thumbnail_url=thumbnail_url,
                    is_authenticated=self.is_authenticated
                )
        except Exception as e:
            logger.error(f"[PC_MUSIC_RESOLVER_ERROR] Failed resolving stream: {e}", exc_info=True)
            return None

    def get_related_tracks(self, video_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Queries YouTube Music for related/watch playlist tracks starting from video_id.
        Returns a list of track metadata dictionaries suitable for queuing.
        """
        if not video_id:
            return []

        logger.info(f"[PC_MUSIC_RELATED] Fetching up to {limit} related tracks for video_id={video_id}")
        related: List[Dict[str, Any]] = []

        # 1. Try ytmusicapi get_watch_playlist
        playlist_data = self._execute_with_ytm(lambda client: client.get_watch_playlist(videoId=video_id, limit=limit + 1))
        if playlist_data and isinstance(playlist_data, dict):
            tracks = playlist_data.get("tracks", [])
            for t in tracks:
                vid = t.get("videoId")
                # Exclude the seed video itself if it's the first track
                if vid and vid != video_id:
                    title = t.get("title", "Unknown Title")
                    artist = "Unknown Artist"
                    artists = t.get("artists")
                    if artists and isinstance(artists, list) and len(artists) > 0:
                        artist = artists[0].get("name", artist)
                    dur = t.get("duration_seconds")
                    thumb = None
                    thumbnails = t.get("thumbnails")
                    if thumbnails and isinstance(thumbnails, list) and len(thumbnails) > 0:
                        thumb = thumbnails[-1].get("url")
                    related.append({
                        "video_id": vid,
                        "title": title,
                        "artist": artist,
                        "duration": dur,
                        "thumbnail_url": thumb
                    })
                    if len(related) >= limit:
                        break
            if related:
                logger.info(f"[PC_MUSIC_RELATED_FOUND] Found {len(related)} related tracks via YTMusic watch playlist.")
                return related

        return related
