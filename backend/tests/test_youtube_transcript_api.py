from youtube_transcript_api._transcripts import (
    FetchedTranscript,
    FetchedTranscriptSnippet,
)

from backend.services import youtube_api


def test_fetch_captions_via_transcript_lib_returns_formatted_segments(monkeypatch) -> None:
    transcript = FetchedTranscript(
        snippets=[
            FetchedTranscriptSnippet(text="Hello", start=1.25, duration=2.5),
            FetchedTranscriptSnippet(text="World", start=3.75, duration=1.0),
        ],
        video_id="abc123",
        language="English",
        language_code="en",
        is_generated=False,
    )

    class FakeTranscriptApi:
        def fetch(self, video_id: str, languages: list[str]):
            assert video_id == "abc123"
            assert languages == ["fr", "en"]
            return transcript

    monkeypatch.setattr(youtube_api, "YouTubeTranscriptApi", FakeTranscriptApi)

    segments = youtube_api.fetch_captions_via_transcript_lib(
        "abc123",
        preferred_langs=["fr", "en"],
    )

    assert segments == [
        {"text": "Hello", "start": 1.25, "end": 3.75},
        {"text": "World", "start": 3.75, "end": 4.75},
    ]
    assert all(isinstance(segment["text"], str) for segment in segments)
    assert all(isinstance(segment["start"], float) for segment in segments)
    assert all(isinstance(segment["end"], float) for segment in segments)


def test_fetch_captions_via_transcript_lib_returns_none_on_exception(monkeypatch) -> None:
    class FakeTranscriptApi:
        def fetch(self, video_id: str, languages: list[str]):
            raise RuntimeError("boom")

    monkeypatch.setattr(youtube_api, "YouTubeTranscriptApi", FakeTranscriptApi)

    assert youtube_api.fetch_captions_via_transcript_lib("abc123") is None


def test_fetch_captions_via_transcript_lib_returns_none_for_empty_transcript(
    monkeypatch,
) -> None:
    transcript = FetchedTranscript(
        snippets=[],
        video_id="abc123",
        language="English",
        language_code="en",
        is_generated=False,
    )

    class FakeTranscriptApi:
        def fetch(self, video_id: str, languages: list[str]):
            return transcript

    monkeypatch.setattr(youtube_api, "YouTubeTranscriptApi", FakeTranscriptApi)

    assert youtube_api.fetch_captions_via_transcript_lib("abc123") is None


def test_fetch_captions_with_source_falls_back_when_transcript_lib_returns_none(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        youtube_api,
        "fetch_captions_via_transcript_lib",
        lambda video_id, preferred_langs=None: None,
    )

    http_calls: list[str] = []

    def fake_http_get(url, **kwargs):
        http_calls.append(url)
        return type(
            "Response",
            (),
            {
                "status_code": 200,
                "json": lambda self: {
                    "items": [{"snippet": {"language": "en", "trackKind": "standard"}}],
                },
            },
        )()

    monkeypatch.setattr(youtube_api.httpx, "get", fake_http_get)
    monkeypatch.setattr(
        youtube_api,
        "_fetch_timedtext_segments",
        lambda video_id, language, asr=False, proxy="": [
            {"start": "1.000", "end": "2.000", "text": "Fallback"}
        ],
    )

    subtitles, source = youtube_api.fetch_captions_with_source(
        "abc123",
        "en",
        "fake-api-key",
    )

    assert subtitles == [{"start": "1.000", "end": "2.000", "text": "Fallback"}]
    assert source == "existing_captions"
    assert any("googleapis.com/youtube/v3/captions" in url for url in http_calls)


def test_handle_youtube_uses_transcript_api_source(monkeypatch) -> None:
    from backend.routers import translate

    monkeypatch.setattr(
        translate,
        "get_video_info",
        lambda video_id, api_key: {"duration_seconds": 120, "title": "Test"},
    )
    monkeypatch.setattr(
        translate,
        "fetch_captions_via_api",
        lambda video_id, target_lang, api_key, **kwargs: (
            [{"start": "00:00:01,000", "end": "00:00:02,000", "text": "Hello"}],
            "youtube_transcript_api",
        ),
    )
    monkeypatch.setattr(
        translate,
        "translate_subtitles_with_metadata",
        lambda subtitles, target_lang, api_key, source_lang=None: {
            "segments": subtitles,
            "detected_language": "en",
            "translation_status": "translated",
        },
    )

    settings = translate.get_settings().model_copy(
        update={"youtube_api_key": "test-youtube-api-key"}
    )
    response = translate._handle_youtube(
        video_id="dQw4w9WgXcQ",
        target_lang="fr",
        settings=settings,
        cache=type("Cache", (), {"store": lambda *args, **kwargs: None})(),
        counter=type(
            "Counter",
            (),
            {
                "increment": lambda *args, **kwargs: None,
                "should_cache": lambda *args, **kwargs: False,
            },
        )(),
    )

    assert response.source == "youtube_transcript_api"
