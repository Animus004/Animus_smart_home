"""
Unit tests for MediaProviderRegistry.
Verifies provider definitions, capability status classifications, and intent resolution.
"""

import pytest
from media_provider_registry import MediaProviderRegistry, ProviderCapabilityStatus, StreamingProvider


@pytest.fixture
def registry():
    return MediaProviderRegistry()


def test_registry_contains_all_audited_providers(registry):
    expected_providers = [
        "youtube", "hotstar", "netflix", "zee5", "apple_tv",
        "airtel_xstream", "sonyliv", "discovery_plus", "hoichoi",
        "mx_player", "prime_video"
    ]
    for pid in expected_providers:
        provider = registry.get_provider(pid)
        assert provider is not None, f"Provider '{pid}' should be registered."
        assert provider.provider_id == pid


def test_youtube_provider_is_autoplay_verified(registry):
    yt = registry.get_provider("youtube")
    assert yt is not None
    assert yt.capability_status == ProviderCapabilityStatus.DIRECT_AUTOPLAY_VERIFIED
    assert yt.autoplay_verified is True
    assert yt.launch_component == "com.amazon.firetv.youtube/dev.cobalt.app.MainActivity"


def test_hotstar_and_netflix_classifications(registry):
    hotstar = registry.get_provider("hotstar")
    assert hotstar.capability_status == ProviderCapabilityStatus.DIRECT_AUTOPLAY_VERIFIED
    assert hotstar.autoplay_verified is True
    assert hotstar.package_name == "in.startv.hotstar"

    netflix = registry.get_provider("netflix")
    assert netflix.capability_status == ProviderCapabilityStatus.DIRECT_LAUNCH_VERIFIED
    assert netflix.package_name == "com.netflix.ninja"


def test_url_provider_detection(registry):
    assert registry.get_provider_for_url("https://www.youtube.com/watch?v=07d2dXHYb94").provider_id == "youtube"
    assert registry.get_provider_for_url("https://youtu.be/07d2dXHYb94").provider_id == "youtube"
    assert registry.get_provider_for_url("https://www.hotstar.com/movies/article-15/1260007886").provider_id == "hotstar"
    assert registry.get_provider_for_url("https://www.netflix.com/watch/81154455").provider_id == "netflix"
    assert registry.get_provider_for_url("https://www.zee5.com/movies/details/uri/0-0-48227").provider_id == "zee5"
    assert registry.get_provider_for_url("https://tv.apple.com/in/movie/ted-lasso/123").provider_id == "apple_tv"
    assert registry.get_provider_for_url("xstream://xstreamplay.com/title/123").provider_id == "airtel_xstream"
    assert registry.get_provider_for_url("https://unknown.com/video/123") is None


def test_resolve_launch_intent_youtube_video_id(registry):
    ok, uri, comp, msg = registry.resolve_launch_intent("youtube", "07d2dXHYb94")
    assert ok is True
    assert uri == "https://www.youtube.com/watch?v=07d2dXHYb94"
    assert comp == "com.amazon.firetv.youtube/dev.cobalt.app.MainActivity"


def test_resolve_launch_intent_unknown_provider(registry):
    ok, uri, comp, msg = registry.resolve_launch_intent("unknown_tv", "12345")
    assert ok is False
    assert "Unknown streaming provider" in msg
