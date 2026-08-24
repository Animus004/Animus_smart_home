"""
Unit tests for SmartRoomContentResolver.
Verifies video ID resolution, explicit provider extraction, and fallback categorization.
"""

import pytest
from unittest.mock import MagicMock
from content_resolver import SmartRoomContentResolver, ResolvedContent
from media_provider_registry import MediaProviderRegistry
from resolver import YouTubeMusicResolver


@pytest.fixture
def mock_music_resolver():
    res = MagicMock(spec=YouTubeMusicResolver)
    res.ytm = MagicMock()
    res._execute_with_ytm.return_value = [
        {"videoId": "07d2dXHYb94", "title": "Article 15 Trailer", "artists": [{"name": "Zee Music"}]}
    ]
    return res


@pytest.fixture
def content_resolver(mock_music_resolver):
    return SmartRoomContentResolver(music_resolver=mock_music_resolver)


def test_resolve_raw_video_id(content_resolver):
    resolved = content_resolver.resolve_content("07d2dXHYb94")
    assert resolved.resolution_type == "DIRECT_VIDEO_ID"
    assert resolved.provider_id == "youtube"
    assert resolved.content_id == "07d2dXHYb94"
    assert resolved.direct_uri == "https://www.youtube.com/watch?v=07d2dXHYb94"
    assert resolved.autoplay_supported is True


def test_resolve_direct_youtube_url(content_resolver):
    resolved = content_resolver.resolve_content("https://www.youtube.com/watch?v=07d2dXHYb94")
    assert resolved.resolution_type == "DIRECT_VIDEO_ID"
    assert resolved.provider_id == "youtube"
    assert resolved.content_id == "07d2dXHYb94"


def test_resolve_explicit_provider_hotstar_phrase(content_resolver):
    resolved = content_resolver.resolve_content("Article 15 on Hotstar")
    assert resolved.provider_id == "hotstar"
    assert resolved.resolution_type == "PROVIDER_DETAILS"
    assert resolved.title == "Article 15"
    assert resolved.autoplay_supported is True
    assert resolved.launch_component == "in.startv.hotstar/com.hotstar.MainActivity"


def test_resolve_explicit_provider_netflix_param(content_resolver):
    resolved = content_resolver.resolve_content("Interstellar", explicit_provider="netflix")
    assert resolved.provider_id == "netflix"
    assert resolved.resolution_type == "PROVIDER_DETAILS"
    assert resolved.title == "Interstellar"
    assert resolved.launch_component == "com.netflix.ninja/.MainActivity"


def test_resolve_catalog_search_to_video_id(content_resolver, mock_music_resolver):
    resolved = content_resolver.resolve_content("Article 15 trailer")
    assert resolved.resolution_type == "DIRECT_VIDEO_ID"
    assert resolved.content_id == "07d2dXHYb94"
    assert resolved.provider_id == "youtube"


def test_resolve_fallback_when_catalog_returns_empty(mock_music_resolver):
    mock_music_resolver._execute_with_ytm.return_value = []
    resolver = SmartRoomContentResolver(music_resolver=mock_music_resolver)
    resolved = resolver.resolve_content("Obscure title without hits")
    assert resolved.resolution_type == "SEARCH_QUERY"
    assert resolved.content_id is None
    assert resolved.title == "Obscure title without hits"
