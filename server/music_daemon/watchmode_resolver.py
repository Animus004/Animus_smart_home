import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional
import requests

logger = logging.getLogger("music_daemon.watchmode_resolver")

SECRETS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "secrets", "watchmode_credentials.json")
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scratch")
CACHE_FILE = os.path.join(CACHE_DIR, "watchmode_cache.json")


class WatchmodeResolver:
    """
    OTT Streaming Metadata and Deep-Link Resolver powered by Watchmode API.
    Resolves title queries to exact provider content IDs and deep-link URLs in region IN (India).
    Includes persistent on-disk caching to conserve API quotas and achieve 0ms lookups.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        region: str = "IN",
        timeout: float = 3.5,
        cache_path: Optional[str] = None
    ):
        self.api_key = api_key or os.environ.get("WATCHMODE_API_KEY")
        self.region = region
        self.timeout = timeout
        self.cache_path = cache_path or CACHE_FILE
        self._cache: Dict[str, Any] = {}

        if not self.api_key:
            self._load_credentials()

        self._load_cache()

    def _load_credentials(self) -> None:
        """Loads API key and settings from secrets file if present."""
        if os.path.exists(SECRETS_PATH):
            try:
                with open(SECRETS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("enabled", True):
                        self.api_key = data.get("api_key")
                        self.region = data.get("region", self.region)
                        logger.info(f"[WATCHMODE] Loaded API key from {SECRETS_PATH} (region={self.region})")
            except Exception as e:
                logger.warning(f"[WATCHMODE] Error reading {SECRETS_PATH}: {e}")

    def _load_cache(self) -> None:
        """Loads cached lookups from disk."""
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    self._cache = json.load(f)
            except Exception as e:
                logger.warning(f"[WATCHMODE] Could not load cache from {self.cache_path}: {e}")
                self._cache = {}

    def _save_cache(self) -> None:
        """Persists memory cache to disk."""
        try:
            os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self._cache, f, indent=2)
        except Exception as e:
            logger.warning(f"[WATCHMODE] Could not save cache to {self.cache_path}: {e}")

    def _extract_content_id(self, provider_key: str, web_url: Optional[str]) -> Optional[str]:
        """Extracts native content ID / numeric ID from provider web URL."""
        if not web_url:
            return None

        p = provider_key.lower()
        if "netflix" in p:
            m = re.search(r'/(?:title|watch)/(\d+)', web_url)
            if m:
                return m.group(1)
        elif "prime" in p or "amazon" in p:
            m = re.search(r'(?:gti=|/detail/)([a-zA-Z0-9._-]+)', web_url)
            if m:
                return m.group(1)
        elif "hotstar" in p:
            m = re.search(r'/(?:movies|in|shows)/(\d+)', web_url)
            if m:
                return m.group(1)
        elif "zee5" in p:
            m = re.search(r'/details/([a-zA-Z0-9_-]+)', web_url)
            if m:
                return m.group(1)

        return web_url

    def resolve_title(self, query: str, target_provider: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Resolves movie or TV show query for the target streaming provider.
        Returns a dictionary with canonical title, year, provider, content_id, and web_url.
        """
        if not query or not query.strip():
            return None

        clean_query = query.strip()
        prov_key = (target_provider or "any").lower().strip()
        cache_key = f"{clean_query.lower()}::{prov_key}::{self.region}"

        # 1. Check cache
        if cache_key in self._cache:
            hit = self._cache[cache_key]
            logger.info(f"[WATCHMODE_CACHE_HIT] Resolved '{clean_query}' via disk cache -> {hit.get('content_id')}")
            return hit

        if not self.api_key:
            logger.debug("[WATCHMODE] No API key available; skipping remote resolution.")
            return None

        t0 = time.time()
        try:
            # 2. Search title via Autocomplete API
            search_url = "https://api.watchmode.com/v1/autocomplete-search/"
            s_resp = requests.get(
                search_url,
                params={
                    "apiKey": self.api_key,
                    "search_value": clean_query,
                    "search_type": 1
                },
                timeout=self.timeout
            )
            if s_resp.status_code != 200:
                logger.warning(f"[WATCHMODE_SEARCH_ERROR] Status {s_resp.status_code}: {s_resp.text}")
                return None

            results = s_resp.json().get("results", [])
            if not results:
                logger.info(f"[WATCHMODE_NO_MATCH] No title results for '{clean_query}'")
                return None

            top = results[0]
            title_id = top.get("id")
            canonical_title = top.get("name", clean_query)
            year = top.get("year")

            # 3. Query sources in target region
            sources_url = f"https://api.watchmode.com/v1/title/{title_id}/sources/"
            src_resp = requests.get(
                sources_url,
                params={
                    "apiKey": self.api_key,
                    "regions": self.region
                },
                timeout=self.timeout
            )
            if src_resp.status_code != 200:
                logger.warning(f"[WATCHMODE_SOURCES_ERROR] Status {src_resp.status_code}")
                return None

            sources = src_resp.json()
            if not isinstance(sources, list) or not sources:
                # Fallback to global sources if region returned empty
                src_resp_global = requests.get(
                    sources_url,
                    params={"apiKey": self.api_key},
                    timeout=self.timeout
                )
                sources = src_resp_global.json() if src_resp_global.status_code == 200 else []

            # 4. Filter and match provider
            matched_source = None
            if isinstance(sources, list):
                for src in sources:
                    src_name = src.get("name", "").lower()
                    if prov_key == "any":
                        matched_source = src
                        break
                    if "netflix" in prov_key and "netflix" in src_name:
                        matched_source = src
                        break
                    elif ("prime" in prov_key or "amazon" in prov_key) and ("amazon" in src_name or "prime" in src_name):
                        matched_source = src
                        break
                    elif ("hotstar" in prov_key or "disney" in prov_key) and ("hotstar" in src_name or "disney" in src_name):
                        matched_source = src
                        break
                    elif "apple" in prov_key and "apple" in src_name:
                        matched_source = src
                        break
                    elif "zee5" in prov_key and "zee5" in src_name:
                        matched_source = src
                        break
                    elif ("sony" in prov_key or "sonyliv" in prov_key) and "sony" in src_name:
                        matched_source = src
                        break

            dur_ms = int((time.time() - t0) * 1000)

            if matched_source:
                web_url = matched_source.get("web_url")
                content_id = self._extract_content_id(prov_key, web_url)
                result = {
                    "title": canonical_title,
                    "year": year,
                    "provider": matched_source.get("name"),
                    "web_url": web_url,
                    "content_id": content_id,
                    "resolution_duration_ms": dur_ms,
                    "source": "watchmode_api"
                }
                logger.info(f"[WATCHMODE_HIT] Resolved '{clean_query}' on {prov_key} -> ID '{content_id}' ({dur_ms}ms)")
                self._cache[cache_key] = result
                self._save_cache()
                return result
            else:
                logger.info(f"[WATCHMODE_NO_PROVIDER_MATCH] '{canonical_title}' not available on '{prov_key}' in {self.region}")
                return None

        except Exception as e:
            logger.warning(f"[WATCHMODE_EXCEPTION] Error resolving '{clean_query}': {e}")
            return None
