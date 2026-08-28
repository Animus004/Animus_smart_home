import json
import pytest
from unittest.mock import patch, MagicMock
from watchmode_resolver import WatchmodeResolver
from fire_tv_controller import FireTvController
from content_resolver import SmartRoomContentResolver


@pytest.fixture
def mock_cache_path(tmp_path):
    return str(tmp_path / "test_watchmode_cache.json")


def test_watchmode_resolver_init(mock_cache_path):
    resolver = WatchmodeResolver(api_key="test_key", region="IN", cache_path=mock_cache_path)
    assert resolver.api_key == "test_key"
    assert resolver.region == "IN"


def test_watchmode_extract_content_id():
    resolver = WatchmodeResolver(api_key="test_key")
    assert resolver._extract_content_id("netflix", "https://www.netflix.com/title/80057281") == "80057281"
    assert resolver._extract_content_id("netflix", "https://www.netflix.com/watch/80018191") == "80018191"
    assert resolver._extract_content_id("prime", "https://app.primevideo.com/detail?gti=amzn1.dv.gti.58a9f7ae") == "amzn1.dv.gti.58a9f7ae"
    assert resolver._extract_content_id("hotstar", "https://www.hotstar.com/in/1971000531") == "1971000531"


def test_watchmode_resolve_title_success_mocked(mock_cache_path):
    resolver = WatchmodeResolver(api_key="test_key", region="IN", cache_path=mock_cache_path)

    mock_search_resp = MagicMock()
    mock_search_resp.status_code = 200
    mock_search_resp.json.return_value = {
        "results": [
            {"id": 3112487, "name": "Stranger Things", "year": 2016}
        ]
    }

    mock_src_resp = MagicMock()
    mock_src_resp.status_code = 200
    mock_src_resp.json.return_value = [
        {
            "name": "Netflix",
            "type": "sub",
            "region": "IN",
            "web_url": "https://www.netflix.com/title/80057281"
        }
    ]

    with patch("requests.get", side_effect=[mock_search_resp, mock_src_resp]):
        res = resolver.resolve_title("Stranger Things", "netflix")
        assert res is not None
        assert res["title"] == "Stranger Things"
        assert res["content_id"] == "80057281"
        assert res["provider"] == "Netflix"

    # Verify disk cache hit
    hit = resolver.resolve_title("Stranger Things", "netflix")
    assert hit is not None
    assert hit["content_id"] == "80057281"


def test_watchmode_resolve_title_api_failure_fallback(mock_cache_path):
    resolver = WatchmodeResolver(api_key="test_key", region="IN", cache_path=mock_cache_path)

    with patch("requests.get", side_effect=Exception("Network error")):
        res = resolver.resolve_title("Unknown Show", "netflix")
        assert res is None


def test_fire_tv_controller_uses_watchmode_for_title_query():
    ftv = FireTvController()
    mock_watchmode = MagicMock()
    mock_watchmode.resolve_title.return_value = {
        "title": "Stranger Things",
        "content_id": "80057281",
        "web_url": "https://www.netflix.com/title/80057281"
    }
    ftv.watchmode = mock_watchmode

    with patch.object(ftv, "wake"), \
         patch.object(ftv, "_run_shell", return_value=(0, "", "")) as mock_shell:
        success = ftv.launch_streaming_provider("netflix", "Stranger Things")
        assert success is True
        mock_watchmode.resolve_title.assert_called_with("Stranger Things", "netflix")
        mock_shell.assert_called_with("am start -a android.intent.action.VIEW -d 'https://www.netflix.com/watch/80057281' -n com.netflix.ninja/.MainActivity")


def test_content_resolver_step5_uses_watchmode():
    mock_watchmode = MagicMock()
    mock_watchmode.resolve_title.return_value = {
        "title": "Stranger Things",
        "content_id": "80057281",
        "web_url": "https://www.netflix.com/title/80057281"
    }
    resolver = SmartRoomContentResolver(watchmode_resolver=mock_watchmode)
    resolved = resolver.resolve_content("Stranger Things on Netflix")

    assert resolved.provider_id == "netflix"
    assert resolved.content_id == "80057281"
    assert resolved.direct_uri == "https://www.netflix.com/title/80057281"
    assert resolved.resolution_type == "PROVIDER_DETAILS"
    assert resolved.confidence == "HIGH"
