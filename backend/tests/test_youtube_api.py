import pytest
import httpx

from types import SimpleNamespace

from backend.services.youtube_api import (
    parse_iso8601_duration,
    get_video_info,
    fetch_captions,
    fetch_captions_via_transcript_lib,
    parse_timedtext_xml,
)


# --- ISO 8601 Duration Parsing ---

def test_parse_iso8601_duration_minutes_and_seconds() -> None:
    assert parse_iso8601_duration("PT1M30S") == 90


def test_parse_iso8601_duration_hours_minutes_seconds() -> None:
    assert parse_iso8601_duration("PT1H2M30S") == 3750


def test_parse_iso8601_duration_seconds_only() -> None:
    assert parse_iso8601_duration("PT45S") == 45


def test_parse_iso8601_duration_minutes_only() -> None:
    assert parse_iso8601_duration("PT5M") == 300


def test_parse_iso8601_duration_hours_only() -> None:
    assert parse_iso8601_duration("PT2H") == 7200


def test_parse_iso8601_duration_zero() -> None:
    assert parse_iso8601_duration("PT0S") == 0


def test_parse_iso8601_duration_invalid_returns_zero() -> None:
    assert parse_iso8601_duration("invalid") == 0


# --- Timedtext XML Parsing ---

def test_parse_timedtext_xml_returns_segments() -> None:
    xml_content = """<?xml version="1.0" encoding="utf-8" ?>
<transcript>
    <text start="0.5" dur="1.2">Hello world</text>
    <text start="2.0" dur="1.5">How are you</text>
</transcript>"""
    result = parse_timedtext_xml(xml_content)
    assert result == [
        {"start": "0.500", "end": "1.700", "text": "Hello world"},
        {"start": "2.000", "end": "3.500", "text": "How are you"},
    ]


def test_parse_timedtext_xml_supports_srv3_paragraph_nodes() -> None:
    xml_content = """<?xml version="1.0" encoding="utf-8" ?>
<timedtext format="3">
    <body>
        <p t="1360" d="1680">[♪♪♪]</p>
        <p t="18640" d="3240">We&#39;re no strangers to love</p>
    </body>
</timedtext>"""

    assert parse_timedtext_xml(xml_content) == [
        {"start": "1.360", "end": "3.040", "text": "[♪♪♪]"},
        {
            "start": "18.640",
            "end": "21.880",
            "text": "We're no strangers to love",
        },
    ]


def test_parse_timedtext_xml_empty_returns_empty() -> None:
    xml_content = """<?xml version="1.0" encoding="utf-8" ?>
<transcript></transcript>"""
    assert parse_timedtext_xml(xml_content) == []


def test_parse_timedtext_xml_handles_html_entities() -> None:
    xml_content = """<?xml version="1.0" encoding="utf-8" ?>
<transcript>
    <text start="1.0" dur="2.0">Tom &amp; Jerry</text>
</transcript>"""
    result = parse_timedtext_xml(xml_content)
    assert result[0]["text"] == "Tom & Jerry"


# --- get_video_info (mocked HTTP) ---

def test_get_video_info_returns_duration_and_captions(monkeypatch) -> None:
    api_response = {
        "items": [{
            "contentDetails": {"duration": "PT3M45S"},
            "snippet": {"title": "Test Video"},
        }]
    }

    def fake_get(url, **kwargs):
        resp = httpx.Response(200, json=api_response)
        return resp

    monkeypatch.setattr(httpx, "get", fake_get)

    info = get_video_info("abc123", "fake-api-key")
    assert info["duration_seconds"] == 225
    assert info["title"] == "Test Video"


def test_get_video_info_returns_none_for_missing_video(monkeypatch) -> None:
    api_response = {"items": []}

    def fake_get(url, **kwargs):
        return httpx.Response(200, json=api_response)

    monkeypatch.setattr(httpx, "get", fake_get)

    info = get_video_info("nonexistent", "fake-api-key")
    assert info is None


def test_get_video_info_raises_on_api_error(monkeypatch) -> None:
    def fake_get(url, **kwargs):
        return httpx.Response(403, json={"error": {"message": "Forbidden"}})

    monkeypatch.setattr(httpx, "get", fake_get)

    with pytest.raises(RuntimeError, match="YouTube API error"):
        get_video_info("abc123", "fake-api-key")


# --- fetch_captions (mocked HTTP) ---

def test_fetch_captions_returns_subtitles_from_timedtext(monkeypatch) -> None:
    captions_response = {
        "items": [
            {"snippet": {"language": "en", "trackKind": "standard"}},
            {"snippet": {"language": "fr", "trackKind": "standard"}},
        ]
    }

    timedtext_xml = """<?xml version="1.0" encoding="utf-8" ?>
<transcript>
    <text start="1.0" dur="2.0">Bonjour</text>
</transcript>"""

    call_log = []

    def fake_get(url, **kwargs):
        call_log.append(url)
        if "googleapis.com" in url:
            return httpx.Response(200, json=captions_response)
        if "timedtext" in url:
            return httpx.Response(200, text=timedtext_xml)
        return httpx.Response(404)

    monkeypatch.setattr(httpx, "get", fake_get)

    result = fetch_captions("abc123", "fr", "fake-api-key")
    assert result == [{"start": "1.000", "end": "3.000", "text": "Bonjour"}]


def test_fetch_captions_falls_back_to_any_language_when_target_missing(monkeypatch) -> None:
    captions_response = {
        "items": [
            {"snippet": {"language": "en", "trackKind": "standard"}},
        ]
    }

    timedtext_xml = """<?xml version="1.0" encoding="utf-8" ?>
<transcript>
    <text start="0.0" dur="1.0">Hello</text>
</transcript>"""

    def fake_get(url, **kwargs):
        if "googleapis.com" in url:
            return httpx.Response(200, json=captions_response)
        if "timedtext" in url:
            return httpx.Response(200, text=timedtext_xml)
        return httpx.Response(404)

    monkeypatch.setattr(httpx, "get", fake_get)

    result = fetch_captions("abc123", "ja", "fake-api-key")
    assert result is not None
    assert result[0]["text"] == "Hello"


def test_fetch_captions_returns_none_when_no_tracks(monkeypatch) -> None:
    captions_response = {"items": []}

    def fake_get(url, **kwargs):
        if "googleapis.com" in url:
            return httpx.Response(200, json=captions_response)
        return httpx.Response(404)

    monkeypatch.setattr(httpx, "get", fake_get)

    result = fetch_captions("abc123", "fr", "fake-api-key")
    assert result is None


def test_fetch_captions_tries_asr_timedtext_when_caption_list_is_empty(monkeypatch) -> None:
    captions_response = {"items": []}
    video_response = {
        "items": [{
            "contentDetails": {"duration": "PT30S"},
            "snippet": {
                "title": "Short",
                "defaultAudioLanguage": "es-ES",
            },
        }]
    }
    asr_xml = """<?xml version="1.0" encoding="utf-8" ?>
<transcript>
    <text start="0.0" dur="1.0">Hola</text>
</transcript>"""
    timedtext_calls: list[dict[str, str]] = []

    def fake_get(url, **kwargs):
        params = kwargs.get("params", {})
        if "googleapis.com/youtube/v3/captions" in url:
            return httpx.Response(200, json=captions_response)
        if "googleapis.com/youtube/v3/videos" in url:
            return httpx.Response(200, json=video_response)
        if "timedtext" in url:
            timedtext_calls.append(dict(params))
            if params == {"v": "abc123", "lang": "es", "fmt": "srv3", "kind": "asr"}:
                return httpx.Response(200, text=asr_xml)
            return httpx.Response(200, text="")
        return httpx.Response(404)

    monkeypatch.setattr(httpx, "get", fake_get)

    result = fetch_captions("abc123", "fr", "fake-api-key")

    assert result == [{"start": "0.000", "end": "1.000", "text": "Hola"}]
    assert timedtext_calls[0] == {
        "v": "abc123",
        "lang": "es",
        "fmt": "srv3",
        "kind": "asr",
    }


def test_fetch_captions_retries_timedtext_with_asr_kind_when_standard_is_empty(monkeypatch) -> None:
    captions_response = {
        "items": [
            {"snippet": {"language": "en", "trackKind": "standard"}},
        ]
    }
    asr_xml = """<?xml version="1.0" encoding="utf-8" ?>
<transcript>
    <text start="2.0" dur="1.0">Generated</text>
</transcript>"""
    timedtext_calls: list[dict[str, str]] = []

    def fake_get(url, **kwargs):
        params = kwargs.get("params", {})
        if "googleapis.com" in url:
            return httpx.Response(200, json=captions_response)
        if "timedtext" in url:
            timedtext_calls.append(dict(params))
            if params == {"v": "abc123", "lang": "en", "fmt": "srv3"}:
                return httpx.Response(200, text="")
            if params == {"v": "abc123", "lang": "en", "fmt": "srv3", "kind": "asr"}:
                return httpx.Response(200, text=asr_xml)
        return httpx.Response(404)

    monkeypatch.setattr(httpx, "get", fake_get)

    result = fetch_captions("abc123", "en", "fake-api-key")

    assert result == [{"start": "2.000", "end": "3.000", "text": "Generated"}]
    assert timedtext_calls == [
        {"v": "abc123", "lang": "en", "fmt": "srv3"},
        {"v": "abc123", "lang": "en", "fmt": "srv3", "kind": "asr"},
    ]


def test_fetch_captions_falls_back_to_ytdlp_on_timedtext_failure(monkeypatch) -> None:
    captions_response = {
        "items": [
            {"snippet": {"language": "en", "trackKind": "standard"}},
        ]
    }

    def fake_get(url, **kwargs):
        if "googleapis.com" in url:
            return httpx.Response(200, json=captions_response)
        if "timedtext" in url:
            return httpx.Response(404)
        return httpx.Response(404)

    monkeypatch.setattr(httpx, "get", fake_get)

    # Mock the yt-dlp fallback
    from backend.services import youtube_api

    monkeypatch.setattr(
        youtube_api,
        "fetch_existing_subtitles",
        lambda url, proxy="", cookie_file=None: [{"start": "00:00:01,000", "end": "00:00:02,000", "text": "Fallback"}],
    )

    result = fetch_captions("abc123", "en", "fake-api-key")
    assert result == [{"start": "00:00:01,000", "end": "00:00:02,000", "text": "Fallback"}]


def test_fetch_captions_passes_proxy_and_cookie_file_to_ytdlp_fallback(monkeypatch) -> None:
    captions_response = {
        "items": [
            {"snippet": {"language": "en", "trackKind": "standard"}},
        ]
    }
    fallback_calls: list[dict[str, object]] = []

    def fake_get(url, **kwargs):
        if "googleapis.com" in url:
            return httpx.Response(200, json=captions_response)
        if "timedtext" in url:
            return httpx.Response(404)
        return httpx.Response(404)

    def fake_fetch_existing_subtitles(url: str, proxy: str = "", cookie_file=None):
        fallback_calls.append({
            "url": url,
            "proxy": proxy,
            "cookie_file": cookie_file,
        })
        return [{"start": "00:00:01,000", "end": "00:00:02,000", "text": "Fallback"}]

    monkeypatch.setattr(httpx, "get", fake_get)
    from backend.services import youtube_api

    monkeypatch.setattr(
        youtube_api,
        "fetch_existing_subtitles",
        fake_fetch_existing_subtitles,
    )

    result = fetch_captions(
        "abc123",
        "en",
        "fake-api-key",
        proxy="http://proxy.test",
        cookie_file="/tmp/cookies.txt",
    )

    assert result == [{"start": "00:00:01,000", "end": "00:00:02,000", "text": "Fallback"}]
    assert fallback_calls == [{
        "url": "https://www.youtube.com/watch?v=abc123",
        "proxy": "http://proxy.test",
        "cookie_file": "/tmp/cookies.txt",
    }]


def test_fetch_captions_via_transcript_lib_retries_after_rotation(monkeypatch) -> None:
    from backend.services import youtube_api

    rotation_calls: list[str] = []
    fetch_calls: list[tuple[str, list[str]]] = []

    class RequestBlocked(Exception):
        pass

    class FakeTranscriptApi:
        def fetch(self, video_id: str, languages: list[str]):
            fetch_calls.append((video_id, list(languages)))
            if len(fetch_calls) == 1:
                raise RequestBlocked("RequestBlocked")
            return SimpleNamespace(
                snippets=[
                    SimpleNamespace(text="Bonjour", start=1.0, duration=2.0),
                ]
            )

    monkeypatch.setattr(youtube_api, "YouTubeTranscriptApi", lambda: FakeTranscriptApi())
    monkeypatch.setattr(youtube_api, "RequestBlocked", RequestBlocked)
    monkeypatch.setattr(
        youtube_api,
        "rotate_warp_ip",
        lambda url: rotation_calls.append(url) or True,
    )
    monkeypatch.setattr(
        youtube_api,
        "get_settings",
        lambda: SimpleNamespace(warp_rotation_url="http://10.0.1.1:40002/rotate"),
    )

    result = fetch_captions_via_transcript_lib("abc123", preferred_langs=["fr"])

    assert result == [{"text": "Bonjour", "start": 1.0, "duration": 2.0}]
    assert fetch_calls == [("abc123", ["fr"]), ("abc123", ["fr"])]
    assert rotation_calls == ["http://10.0.1.1:40002/rotate"]


def test_fetch_captions_via_transcript_lib_returns_none_when_rotation_fails(monkeypatch) -> None:
    from backend.services import youtube_api

    class RequestBlocked(Exception):
        pass

    class FakeTranscriptApi:
        def fetch(self, video_id: str, languages: list[str]):
            raise RequestBlocked("RequestBlocked")

    monkeypatch.setattr(youtube_api, "YouTubeTranscriptApi", lambda: FakeTranscriptApi())
    monkeypatch.setattr(youtube_api, "RequestBlocked", RequestBlocked)
    monkeypatch.setattr(youtube_api, "rotate_warp_ip", lambda url: False)
    monkeypatch.setattr(
        youtube_api,
        "get_settings",
        lambda: SimpleNamespace(warp_rotation_url="http://10.0.1.1:40002/rotate"),
    )

    assert fetch_captions_via_transcript_lib("abc123", preferred_langs=["fr"]) is None
