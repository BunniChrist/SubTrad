import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from backend.main import app


client = TestClient(app)


class FakeSubtitleCache:
    storage: dict[tuple[str, str], dict[str, object]] = {}
    init_paths: list[str] = []

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        type(self).init_paths.append(db_path)

    @classmethod
    def reset(cls) -> None:
        cls.storage = {}
        cls.init_paths = []

    def store(self, video_id: str, target_lang: str, response_data: dict[str, object]) -> None:
        type(self).storage[(video_id, target_lang)] = response_data.copy()

    def retrieve(self, video_id: str, target_lang: str) -> dict[str, object] | None:
        cached = type(self).storage.get((video_id, target_lang))
        return cached.copy() if cached is not None else None

    def exists(self, video_id: str, target_lang: str) -> bool:
        return (video_id, target_lang) in type(self).storage


class FakeRequestCounter:
    counts: dict[tuple[str, str], int] = {}
    init_calls: list[tuple[str, int]] = []

    def __init__(self, db_path: str, threshold: int) -> None:
        self.db_path = db_path
        self.threshold = threshold
        type(self).init_calls.append((db_path, threshold))

    @classmethod
    def reset(cls) -> None:
        cls.counts = {}
        cls.init_calls = []

    def increment(self, video_id: str, target_lang: str) -> int:
        key = (video_id, target_lang)
        next_count = type(self).counts.get(key, 0) + 1
        type(self).counts[key] = next_count
        return next_count

    def get_count(self, video_id: str, target_lang: str) -> int:
        return type(self).counts.get((video_id, target_lang), 0)

    def should_cache(self, video_id: str, target_lang: str) -> bool:
        return self.get_count(video_id, target_lang) >= self.threshold


def test_fetch_video_duration_seconds_ignores_missing_formats(monkeypatch) -> None:
    from backend.routers import translate

    captured_options: dict[str, object] = {}

    class FakeYoutubeDL:
        def __init__(self, options: dict[str, object]) -> None:
            captured_options.update(options)

        def __enter__(self) -> "FakeYoutubeDL":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

        def extract_info(self, url: str, download: bool = False) -> dict[str, object]:
            return {"duration": 213}

    monkeypatch.setattr(translate, "YoutubeDL", FakeYoutubeDL)

    duration = translate.fetch_video_duration_seconds(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    )

    assert duration == 213
    assert captured_options["ignore_no_formats_error"] is True


def test_translate_rejects_invalid_urls() -> None:
    response = client.post(
        "/api/translate",
        json={"url": "https://example.com/video/123", "target_lang": "fr"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported video URL"


def test_translate_rejects_unsupported_languages() -> None:
    response = client.post(
        "/api/translate",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "target_lang": "de",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported target language"


def test_transcribe_media_url_returns_translate_compatible_payload(monkeypatch) -> None:
    from backend.routers import translate

    FakeSubtitleCache.reset()
    FakeRequestCounter.reset()
    monkeypatch.setattr(translate, "SubtitleCache", FakeSubtitleCache)
    monkeypatch.setattr(translate, "RequestCounter", FakeRequestCounter)
    cleanup_calls: list[str] = []

    monkeypatch.setattr(
        translate,
        "download_media_url",
        lambda media_url, timeout=60.0: "/tmp/subtrad/apify_video.mp4",
    )
    monkeypatch.setattr(
        translate,
        "get_video_info",
        lambda video_id, api_key: {"duration_seconds": 120, "title": "Recovered Video"},
    )
    monkeypatch.setattr(
        translate,
        "transcribe_audio_with_metadata",
        lambda audio_path: {
            "segments": [{"start": 0.0, "end": 1.5, "text": "Hello"}],
            "language": "en",
            "timings": {"preprocess_seconds": 0.2, "transcription_seconds": 0.5},
        },
    )
    monkeypatch.setattr(
        translate,
        "translate_subtitles_with_metadata",
        lambda subtitles, target_lang, api_key, source_lang=None: {
            "segments": [{"start": 0.0, "end": 1.5, "text": "Bonjour"}],
            "detected_language": source_lang,
            "translation_status": "translated",
        },
    )
    monkeypatch.setattr(
        translate,
        "cleanup_audio",
        lambda audio_path: cleanup_calls.append(audio_path),
    )

    response = client.post(
        "/api/transcribe-media-url",
        json={
            "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "media_url": "https://cdn.example.com/video.mp4",
            "target_lang": "fr",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["platform"] == "youtube"
    assert data["video_id"] == "dQw4w9WgXcQ"
    assert data["source"] == "whisper_transcription"
    assert data["needs_transcription"] is True
    assert data["duration_seconds"] == 120
    assert data["subtitles"] == [{"start": 0.0, "end": 1.5, "text": "Bonjour"}]
    assert data["exports"]["txt"] == "Hello"
    assert cleanup_calls == ["/tmp/subtrad/apify_video.mp4"]


def test_transcribe_media_url_rejects_invalid_source_url() -> None:
    response = client.post(
        "/api/transcribe-media-url",
        json={
            "source_url": "https://example.com/video/123",
            "media_url": "https://cdn.example.com/video.mp4",
            "target_lang": "fr",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unsupported video URL"


def test_transcribe_media_url_returns_422_when_media_download_fails(monkeypatch) -> None:
    from backend.routers import translate

    FakeSubtitleCache.reset()
    FakeRequestCounter.reset()
    monkeypatch.setattr(translate, "SubtitleCache", FakeSubtitleCache)
    monkeypatch.setattr(translate, "RequestCounter", FakeRequestCounter)
    monkeypatch.setattr(
        translate,
        "download_media_url",
        lambda media_url, timeout=60.0: (_ for _ in ()).throw(RuntimeError("403")),
    )

    response = client.post(
        "/api/transcribe-media-url",
        json={
            "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "media_url": "https://cdn.example.com/video.mp4",
            "target_lang": "fr",
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Could not extract audio from this video.",
        "error_code": "audio_extraction_failed",
    }


def test_transcribe_media_url_logs_download_failure(monkeypatch, caplog) -> None:
    from backend.routers import translate

    FakeSubtitleCache.reset()
    FakeRequestCounter.reset()
    monkeypatch.setattr(translate, "SubtitleCache", FakeSubtitleCache)
    monkeypatch.setattr(translate, "RequestCounter", FakeRequestCounter)
    monkeypatch.setattr(
        translate,
        "download_media_url",
        lambda media_url, timeout=60.0: (_ for _ in ()).throw(RuntimeError("403 forbidden")),
    )

    with caplog.at_level("WARNING"):
        response = client.post(
            "/api/transcribe-media-url",
            json={
                "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "media_url": "https://cdn.example.com/video.mp4",
                "target_lang": "fr",
            },
        )

    assert response.status_code == 422
    assert "External media download failed" in caplog.text
    assert "video_id=dQw4w9WgXcQ" in caplog.text


def test_transcribe_local_file_returns_translate_compatible_payload(monkeypatch, tmp_path) -> None:
    from backend.routers import translate

    FakeSubtitleCache.reset()
    FakeRequestCounter.reset()
    monkeypatch.setattr(translate, "SubtitleCache", FakeSubtitleCache)
    monkeypatch.setattr(translate, "RequestCounter", FakeRequestCounter)
    local_audio = tmp_path / "dQw4w9WgXcQ.mp3"
    local_audio.write_bytes(b"fake mp3 bytes")
    cleanup_calls: list[str] = []

    monkeypatch.setattr(
        translate,
        "get_video_info",
        lambda video_id, api_key: {"duration_seconds": 120, "title": "Recovered Video"},
    )
    monkeypatch.setattr(
        translate,
        "transcribe_audio_with_metadata",
        lambda audio_path: {
            "segments": [{"start": 0.0, "end": 1.5, "text": "Hello"}],
            "language": "en",
            "timings": {"preprocess_seconds": 0.2, "transcription_seconds": 0.5},
        },
    )
    monkeypatch.setattr(
        translate,
        "translate_subtitles_with_metadata",
        lambda subtitles, target_lang, api_key, source_lang=None: {
            "segments": [{"start": 0.0, "end": 1.5, "text": "Bonjour"}],
            "detected_language": source_lang,
            "translation_status": "translated",
        },
    )
    monkeypatch.setattr(
        translate,
        "cleanup_audio",
        lambda audio_path: cleanup_calls.append(audio_path),
    )

    response = client.post(
        "/api/transcribe-local-file",
        json={
            "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "file_path": str(local_audio),
            "target_lang": "fr",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["platform"] == "youtube"
    assert data["video_id"] == "dQw4w9WgXcQ"
    assert data["source"] == "whisper_transcription"
    assert data["needs_transcription"] is True
    assert data["duration_seconds"] == 120
    assert data["subtitles"] == [{"start": 0.0, "end": 1.5, "text": "Bonjour"}]
    assert data["exports"]["txt"] == "Hello"
    assert len(cleanup_calls) == 1
    assert cleanup_calls[0] != str(local_audio)
    assert local_audio.exists() is True


def test_transcribe_local_file_stages_copy_before_transcription(monkeypatch, tmp_path) -> None:
    from backend.routers import translate

    FakeSubtitleCache.reset()
    FakeRequestCounter.reset()
    monkeypatch.setattr(translate, "SubtitleCache", FakeSubtitleCache)
    monkeypatch.setattr(translate, "RequestCounter", FakeRequestCounter)
    source_audio = tmp_path / "dQw4w9WgXcQ.mp3"
    source_audio.write_bytes(b"fake mp3 bytes")
    seen_audio_paths: list[str] = []
    cleanup_calls: list[str] = []

    monkeypatch.setattr(
        translate,
        "get_video_info",
        lambda video_id, api_key: {"duration_seconds": 120, "title": "Recovered Video"},
    )

    def fake_transcribe(audio_path: str) -> dict[str, object]:
        seen_audio_paths.append(audio_path)
        assert audio_path != str(source_audio)
        assert Path(audio_path).exists()
        assert Path(audio_path).read_bytes() == source_audio.read_bytes()
        return {
            "segments": [{"start": 0.0, "end": 1.5, "text": "Hello"}],
            "language": "en",
            "timings": {"preprocess_seconds": 0.2, "transcription_seconds": 0.5},
        }

    monkeypatch.setattr(translate, "transcribe_audio_with_metadata", fake_transcribe)
    monkeypatch.setattr(
        translate,
        "translate_subtitles_with_metadata",
        lambda subtitles, target_lang, api_key, source_lang=None: {
            "segments": [{"start": 0.0, "end": 1.5, "text": "Bonjour"}],
            "detected_language": source_lang,
            "translation_status": "translated",
        },
    )
    monkeypatch.setattr(
        translate,
        "cleanup_audio",
        lambda audio_path: cleanup_calls.append(audio_path),
    )

    response = client.post(
        "/api/transcribe-local-file",
        json={
            "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "file_path": str(source_audio),
            "target_lang": "fr",
        },
    )

    assert response.status_code == 200
    assert seen_audio_paths and seen_audio_paths[0] != str(source_audio)
    assert cleanup_calls == seen_audio_paths
    assert source_audio.exists() is True


def test_transcribe_local_file_returns_422_when_local_file_is_missing(monkeypatch) -> None:
    from backend.routers import translate

    FakeSubtitleCache.reset()
    FakeRequestCounter.reset()
    monkeypatch.setattr(translate, "SubtitleCache", FakeSubtitleCache)
    monkeypatch.setattr(translate, "RequestCounter", FakeRequestCounter)

    response = client.post(
        "/api/transcribe-local-file",
        json={
            "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "file_path": "/tmp/does-not-exist.mp3",
            "target_lang": "fr",
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Local audio file not found.",
        "error_code": "audio_file_not_found",
    }


def test_translate_allows_videos_up_to_five_hours(monkeypatch) -> None:
    from backend.routers import translate

    FakeSubtitleCache.reset()
    FakeRequestCounter.reset()
    monkeypatch.setattr(translate, "SubtitleCache", FakeSubtitleCache)
    monkeypatch.setattr(translate, "RequestCounter", FakeRequestCounter)
    monkeypatch.setattr(
        translate,
        "get_video_info",
        lambda video_id, api_key: {"duration_seconds": 18_000, "title": "Long Video"},
    )
    monkeypatch.setattr(
        translate,
        "fetch_captions_via_api",
        lambda video_id, target_lang, api_key, **kwargs: [
            {"start": "00:00:01,000", "end": "00:00:02,000", "text": "Hello"}
        ],
    )
    monkeypatch.setattr(
        translate,
        "translate_subtitles_with_metadata",
        lambda subtitles, target_lang, api_key, source_lang=None: {
            "segments": [{"start": "1.0", "end": "2.0", "text": "Bonjour"}],
            "detected_language": "en",
            "translation_status": "translated",
        },
    )

    response = client.post(
        "/api/translate",
        json={
            "url": "https://www.youtube.com/watch?v=abc123xyz89",
            "target_lang": "fr",
        },
    )

    assert response.status_code == 200
    assert response.json()["duration_seconds"] == 18_000


def test_translate_returns_premium_redirect_for_videos_over_five_hours(monkeypatch) -> None:
    from backend.routers import translate

    FakeSubtitleCache.reset()
    FakeRequestCounter.reset()
    monkeypatch.setattr(translate, "SubtitleCache", FakeSubtitleCache)
    monkeypatch.setattr(translate, "RequestCounter", FakeRequestCounter)
    monkeypatch.setattr(
        translate,
        "get_video_info",
        lambda video_id, api_key: {"duration_seconds": 18_001, "title": "Long Video"},
    )

    response = client.post(
        "/api/translate",
        json={
            "url": "https://www.youtube.com/watch?v=abc123xyz90",
            "target_lang": "fr",
        },
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Video exceeds maximum duration",
        "redirect": "premium",
        "duration_seconds": 18_001,
    }


def test_translate_returns_clear_error_when_metadata_lookup_fails(monkeypatch) -> None:
    from backend.routers import translate

    def raise_metadata_error(video_id: str, api_key: str):
        raise RuntimeError("Metadata lookup blocked")

    monkeypatch.setattr(translate, "get_video_info", raise_metadata_error)

    response = client.post(
        "/api/translate",
        json={
            "url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
            "target_lang": "fr",
        },
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Video metadata lookup failed",
        "error": "Metadata lookup blocked",
    }


def test_translate_returns_existing_subtitles(monkeypatch) -> None:
    from backend.routers import translate

    settings = translate.get_settings().model_copy(
        update={
            "youtube_api_key": "test-youtube-api-key",
            "openai_api_key": "test-openai-key",
        }
    )
    monkeypatch.setattr(
        translate,
        "get_video_info",
        lambda video_id, api_key: {"duration_seconds": 120, "title": "Test"},
    )
    monkeypatch.setattr(
        translate,
        "fetch_captions_via_api",
        lambda video_id, target_lang, api_key, **kwargs: [
            {"start": "00:00:01,000", "end": "00:00:02,000", "text": "Hello"}
        ],
    )
    monkeypatch.setattr(
        translate,
        "translate_subtitles_with_metadata",
        lambda subtitles, target_lang, api_key, source_lang=None: {
            "segments": [{"start": "1.0", "end": "2.0", "text": "Bonjour"}],
            "detected_language": "en",
            "translation_status": "translated",
        },
    )
    response = translate._handle_youtube(
        video_id="dQw4w9WgXcQ",
        target_lang="fr",
        settings=settings,
        cache=FakeSubtitleCache("data/test-cache.db"),
        counter=FakeRequestCounter("data/test-cache.db", threshold=100),
    )

    assert response.model_dump() == {
        "platform": "youtube",
        "video_id": "dQw4w9WgXcQ",
        "subtitles": [{"start": "1.0", "end": "2.0", "text": "Bonjour"}],
        "duration_seconds": 120,
        "needs_transcription": False,
        "source": "existing_captions",
        "target_lang": "fr",
        "detected_language": "en",
        "translation_status": "translated",
        "exports": {
            "vtt": "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nBonjour\n",
            "txt": "Bonjour",
            "md": (
                "---\n"
                "title: youtube-dQw4w9WgXcQ\n"
                "platform: youtube\n"
                "video_id: dQw4w9WgXcQ\n"
                "language: en\n"
                f"date: {__import__('datetime').date.today().isoformat()}\n"
                "---\n\n"
                "[00:00] Bonjour"
            ),
        },
    }


def test_translate_module_uses_dispatch_translation_backend() -> None:
    from backend.routers import translate

    assert (
        translate.translate_subtitles_with_metadata.__module__
        == "backend.services.translator_dispatch"
    )


def test_handle_youtube_passes_cookie_file_and_proxy_to_caption_fetch(monkeypatch, tmp_path) -> None:
    from backend.routers import translate

    captured_call: dict[str, object] = {}
    cookie_file = tmp_path / "yt_cookies.txt"
    cookie_file.write_text("youtube-cookie")
    FakeSubtitleCache.reset()
    FakeRequestCounter.reset()

    monkeypatch.setattr(
        translate,
        "YOUTUBE_COOKIE_FILE",
        cookie_file,
    )
    monkeypatch.setattr(
        translate,
        "get_video_info",
        lambda video_id, api_key: {"duration_seconds": 120, "title": "Test"},
    )

    def fake_fetch_captions(video_id, target_lang, api_key, proxy="", cookie_file=None):
        captured_call.update({
            "video_id": video_id,
            "target_lang": target_lang,
            "api_key": api_key,
            "proxy": proxy,
            "cookie_file": cookie_file,
        })
        return [{"start": "00:00:01,000", "end": "00:00:02,000", "text": "Hello"}]

    monkeypatch.setattr(translate, "fetch_captions_via_api", fake_fetch_captions)
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
        update={
            "youtube_api_key": "test-youtube-api-key",
            "proxy_url": "http://proxy.test",
        }
    )
    response = translate._handle_youtube(
        video_id="dQw4w9WgXcQ",
        target_lang="fr",
        settings=settings,
        cache=FakeSubtitleCache("data/test-cache.db"),
        counter=FakeRequestCounter("data/test-cache.db", threshold=100),
    )

    assert response.video_id == "dQw4w9WgXcQ"
    assert captured_call == {
        "video_id": "dQw4w9WgXcQ",
        "target_lang": "fr",
        "api_key": "test-youtube-api-key",
        "proxy": "http://proxy.test",
        "cookie_file": str(cookie_file),
    }


def test_translate_runs_whisper_fallback_when_subtitles_are_missing(monkeypatch) -> None:
    """Whisper fallback applies to non-YouTube platforms (TikTok/Instagram)."""
    from backend.routers import translate

    monkeypatch.setattr(
        translate,
        "fetch_video_duration_seconds",
        lambda url, proxy="": 120,
    )
    monkeypatch.setattr(
        translate,
        "fetch_existing_subtitles",
        lambda url, proxy="": None,
    )
    monkeypatch.setattr(
        translate,
        "extract_audio",
        lambda url, video_id, proxy="": f"/tmp/subtrad/{video_id}.m4a",
    )
    monkeypatch.setattr(
        translate,
        "transcribe_audio_with_metadata",
        lambda audio_path: {
            "segments": [{"start": 0.0, "end": 1.5, "text": "Hello world 😀"}],
            "language": "en",
            "timings": {"preprocess_seconds": 0.11, "transcription_seconds": 0.42},
        },
    )
    monkeypatch.setattr(
        translate,
        "translate_subtitles_with_metadata",
        lambda subtitles, target_lang, api_key, source_lang=None: {
            "segments": [{"start": 0.0, "end": 1.5, "text": "Bonjour le monde"}],
            "detected_language": source_lang,
            "translation_status": "translated",
        },
    )
    cleanup_calls: list[str] = []
    monkeypatch.setattr(
        translate,
        "cleanup_audio",
        lambda audio_path: cleanup_calls.append(audio_path),
    )

    response = client.post(
        "/api/translate",
        json={
            "url": "https://www.tiktok.com/@user/video/1234567890",
            "target_lang": "ja",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["platform"] == "tiktok"
    assert data["needs_transcription"] is True
    assert data["source"] == "whisper_transcription"
    assert data["translation_status"] == "translated"
    assert data["exports"] == {
        "vtt": "WEBVTT\n\n00:00:00.000 --> 00:00:01.500\nHello world 😀\n",
        "txt": "Hello world 😀",
        "md": (
            "---\n"
            "title: tiktok-1234567890\n"
            "platform: tiktok\n"
            "video_id: 1234567890\n"
            "language: en\n"
            f"date: {__import__('datetime').date.today().isoformat()}\n"
            "---\n\n"
            "[00:00] Hello world 😀"
        ),
    }


def test_translate_returns_clear_error_when_transcription_fails(monkeypatch) -> None:
    """Transcription errors apply to non-YouTube platforms."""
    from backend.routers import translate

    settings = translate.get_settings().model_copy(update={"openai_api_key": "test-openai-key"})
    monkeypatch.setattr(translate, "fetch_video_duration_seconds", lambda url, proxy="": 120)
    monkeypatch.setattr(translate, "fetch_existing_subtitles", lambda url, proxy="": None)
    monkeypatch.setattr(
        translate,
        "extract_audio",
        lambda url, video_id, proxy="": f"/tmp/subtrad/{video_id}.m4a",
    )
    cleanup_calls: list[str] = []
    monkeypatch.setattr(
        translate,
        "cleanup_audio",
        lambda audio_path: cleanup_calls.append(audio_path),
    )

    def raise_transcription_error(audio_path: str) -> dict[str, object]:
        raise ValueError("Audio preprocessing failed: invalid header")

    monkeypatch.setattr(
        translate,
        "transcribe_audio_with_metadata",
        raise_transcription_error,
    )

    with pytest.raises(translate.ApiError) as exc_info:
        translate._handle_ytdlp(
            url="https://www.tiktok.com/@user/video/1234567890",
            platform="tiktok",
            video_id="1234567890",
            target_lang="ja",
            settings=settings,
            cache=FakeSubtitleCache("data/test-cache.db"),
            counter=FakeRequestCounter("data/test-cache.db", threshold=100),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == {
        "detail": "Audio transcription failed.",
        "error_code": "audio_transcription_failed",
    }
    assert cleanup_calls == ["/tmp/subtrad/1234567890.m4a"]


def test_translate_returns_skipped_status_when_source_matches_target(monkeypatch) -> None:
    from backend.routers import translate

    monkeypatch.setattr(
        translate,
        "get_video_info",
        lambda video_id, api_key: {"duration_seconds": 120, "title": "Test"},
    )
    monkeypatch.setattr(
        translate,
        "fetch_captions_via_api",
        lambda video_id, target_lang, api_key, **kwargs: [
            {"start": "00:00:01,000", "end": "00:00:02,000", "text": "Hello"}
        ],
    )
    monkeypatch.setattr(
        translate,
        "translate_subtitles_with_metadata",
        lambda subtitles, target_lang, api_key, source_lang=None: {
            "segments": subtitles,
            "detected_language": "en",
            "translation_status": "skipped_same_lang",
        },
    )

    response = client.post(
        "/api/translate",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "target_lang": "en",
        },
    )

    assert response.status_code == 200
    assert response.json()["translation_status"] == "skipped_same_lang"
    assert response.json()["detected_language"] == "en"


def test_translate_returns_original_subtitles_with_warning_when_translation_fails(
    monkeypatch,
) -> None:
    from backend.routers import translate

    FakeSubtitleCache.reset()
    FakeRequestCounter.reset()
    monkeypatch.setattr(translate, "SubtitleCache", FakeSubtitleCache)
    monkeypatch.setattr(translate, "RequestCounter", FakeRequestCounter)
    original_subtitles = [{"start": "00:00:01,000", "end": "00:00:02,000", "text": "Hello"}]
    monkeypatch.setattr(
        translate,
        "get_video_info",
        lambda video_id, api_key: {"duration_seconds": 120, "title": "Test"},
    )
    monkeypatch.setattr(
        translate,
        "fetch_captions_via_api",
        lambda video_id, target_lang, api_key, **kwargs: original_subtitles,
    )
    monkeypatch.setattr(
        translate,
        "translate_subtitles_with_metadata",
        lambda subtitles, target_lang, api_key, source_lang=None: {
            "segments": subtitles,
            "detected_language": "en",
            "translation_status": "failed_fallback_original",
        },
    )

    response = client.post(
        "/api/translate",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "target_lang": "fr",
        },
    )

    assert response.status_code == 200
    assert response.json()["subtitles"] == original_subtitles
    assert response.json()["translation_status"] == "failed_fallback_original"


def test_translate_processes_normally_before_cache_threshold(monkeypatch) -> None:
    from backend.config import Settings
    from backend.routers import translate

    FakeSubtitleCache.reset()
    FakeRequestCounter.reset()

    monkeypatch.setattr(
        translate,
        "get_settings",
        lambda: Settings(
            cache_db_path="data/test-cache.db",
            cache_threshold=2,
            supported_languages=["fr", "es", "en", "ja"],
        ),
    )
    monkeypatch.setattr(translate, "SubtitleCache", FakeSubtitleCache)
    monkeypatch.setattr(translate, "RequestCounter", FakeRequestCounter)
    monkeypatch.setattr(
        translate,
        "get_video_info",
        lambda video_id, api_key: {"duration_seconds": 120, "title": "Test"},
    )
    monkeypatch.setattr(
        translate,
        "fetch_captions_via_api",
        lambda video_id, target_lang, api_key, **kwargs: [
            {"start": "00:00:01,000", "end": "00:00:02,000", "text": "Hello"}
        ],
    )
    monkeypatch.setattr(
        translate,
        "translate_subtitles_with_metadata",
        lambda subtitles, target_lang, api_key, source_lang=None: {
            "segments": [{"start": "00:00:01,000", "end": "00:00:02,000", "text": "Bonjour"}],
            "detected_language": "en",
            "translation_status": "translated",
        },
    )

    response = client.post(
        "/api/translate",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "target_lang": "fr",
        },
    )

    assert response.status_code == 200
    assert response.json()["translation_status"] == "translated"
    assert response.json()["needs_transcription"] is False
    assert FakeRequestCounter.counts[("dQw4w9WgXcQ", "fr")] == 1
    assert FakeSubtitleCache.storage == {}
    assert FakeSubtitleCache.init_paths == ["data/test-cache.db"]
    assert FakeRequestCounter.init_calls == [("data/test-cache.db", 2)]


def test_translate_returns_cached_response_after_threshold(monkeypatch) -> None:
    from backend.config import Settings
    from backend.routers import translate

    FakeSubtitleCache.reset()
    FakeRequestCounter.reset()

    translation_calls: list[str] = []

    monkeypatch.setattr(
        translate,
        "get_settings",
        lambda: Settings(
            cache_db_path="data/test-cache.db",
            cache_threshold=2,
            supported_languages=["fr", "es", "en", "ja"],
        ),
    )
    monkeypatch.setattr(translate, "SubtitleCache", FakeSubtitleCache)
    monkeypatch.setattr(translate, "RequestCounter", FakeRequestCounter)
    monkeypatch.setattr(
        translate,
        "get_video_info",
        lambda video_id, api_key: {"duration_seconds": 120, "title": "Test"},
    )
    monkeypatch.setattr(
        translate,
        "fetch_captions_via_api",
        lambda video_id, target_lang, api_key, **kwargs: [
            {"start": "00:00:01,000", "end": "00:00:02,000", "text": "Hello"}
        ],
    )

    def fake_translate_subtitles(subtitles, target_lang, api_key, source_lang=None):
        translation_calls.append(target_lang)
        return {
            "segments": [{"start": "00:00:01,000", "end": "00:00:02,000", "text": "Bonjour"}],
            "detected_language": "en",
            "translation_status": "translated",
        }

    monkeypatch.setattr(
        translate,
        "translate_subtitles_with_metadata",
        fake_translate_subtitles,
    )

    first_response = client.post(
        "/api/translate",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "target_lang": "fr",
        },
    )
    second_response = client.post(
        "/api/translate",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "target_lang": "fr",
        },
    )
    third_response = client.post(
        "/api/translate",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "target_lang": "fr",
        },
    )

    assert first_response.status_code == 200
    assert first_response.json()["translation_status"] == "translated"
    assert second_response.status_code == 200
    assert second_response.json()["translation_status"] == "translated"
    assert FakeRequestCounter.counts[("dQw4w9WgXcQ", "fr")] == 2
    assert FakeSubtitleCache.exists(
        FakeSubtitleCache("data/test-cache.db"),
        "dQw4w9WgXcQ",
        "fr",
    )
    assert third_response.status_code == 200
    assert third_response.json()["translation_status"] == "cached"
    assert third_response.json()["subtitles"] == [
        {"start": "00:00:01,000", "end": "00:00:02,000", "text": "Bonjour"}
    ]
    assert translation_calls == ["fr", "fr"]


# --- YouTube API v3 integration tests ---


def test_youtube_uses_api_for_duration_and_captions(monkeypatch) -> None:
    """YouTube videos should use YouTube API v3 instead of yt-dlp."""
    from backend.routers import translate

    monkeypatch.setattr(
        translate,
        "get_video_info",
        lambda video_id, api_key: {"duration_seconds": 180, "title": "Test"},
    )
    monkeypatch.setattr(
        translate,
        "fetch_captions_via_api",
        lambda video_id, target_lang, api_key, **kwargs: [
            {"start": "1.000", "end": "3.000", "text": "Bonjour"}
        ],
    )
    monkeypatch.setattr(
        translate,
        "translate_subtitles_with_metadata",
        lambda subtitles, target_lang, api_key, source_lang=None: {
            "segments": [{"start": "1.000", "end": "3.000", "text": "Hola"}],
            "detected_language": "fr",
            "translation_status": "translated",
        },
    )

    response = client.post(
        "/api/translate",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "target_lang": "es",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["platform"] == "youtube"
    assert data["duration_seconds"] == 180
    assert data["source"] == "existing_captions"
    assert data["subtitles"] == [{"start": "1.000", "end": "3.000", "text": "Hola"}]


def test_youtube_no_captions_falls_back_to_whisper(monkeypatch) -> None:
    """YouTube videos with no captions should use Whisper transcription."""
    from backend.routers import translate

    FakeSubtitleCache.reset()
    FakeRequestCounter.reset()
    monkeypatch.setattr(translate, "SubtitleCache", FakeSubtitleCache)
    monkeypatch.setattr(translate, "RequestCounter", FakeRequestCounter)
    cleanup_calls: list[str] = []

    monkeypatch.setattr(
        translate,
        "get_video_info",
        lambda video_id, api_key: {"duration_seconds": 120, "title": "No Subs"},
    )
    monkeypatch.setattr(
        translate,
        "fetch_captions_via_api",
        lambda video_id, target_lang, api_key, **kwargs: None,
    )
    monkeypatch.setattr(
        translate,
        "extract_audio",
        lambda url, video_id, proxy="": f"/tmp/subtrad/{video_id}.m4a",
    )
    monkeypatch.setattr(
        translate,
        "transcribe_audio_with_metadata",
        lambda audio_path: {
            "segments": [{"start": 0.0, "end": 1.5, "text": "Hello"}],
            "language": "en",
            "timings": {"preprocess_seconds": 0.12, "transcription_seconds": 0.41},
        },
    )
    monkeypatch.setattr(
        translate,
        "translate_subtitles_with_metadata",
        lambda subtitles, target_lang, api_key, source_lang=None: {
            "segments": [{"start": 0.0, "end": 1.5, "text": "Bonjour"}],
            "detected_language": source_lang,
            "translation_status": "translated",
        },
    )
    monkeypatch.setattr(
        translate,
        "cleanup_audio",
        lambda audio_path: cleanup_calls.append(audio_path),
    )

    response = client.post(
        "/api/translate",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "target_lang": "fr",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "whisper_transcription"
    assert data["needs_transcription"] is True
    assert data["exports"] == {
        "vtt": "WEBVTT\n\n00:00:00.000 --> 00:00:01.500\nHello\n",
        "txt": "Hello",
        "md": (
            "---\n"
            "title: youtube-dQw4w9WgXcQ\n"
            "platform: youtube\n"
            "video_id: dQw4w9WgXcQ\n"
            "language: en\n"
            f"date: {__import__('datetime').date.today().isoformat()}\n"
            "---\n\n"
            "[00:00] Hello"
        ),
    }
    assert cleanup_calls == ["/tmp/subtrad/dQw4w9WgXcQ.m4a"]


def test_youtube_caption_fetch_exception_falls_back_to_whisper(monkeypatch) -> None:
    from backend.routers import translate

    FakeSubtitleCache.reset()
    FakeRequestCounter.reset()
    monkeypatch.setattr(translate, "SubtitleCache", FakeSubtitleCache)
    monkeypatch.setattr(translate, "RequestCounter", FakeRequestCounter)
    cleanup_calls: list[str] = []

    monkeypatch.setattr(
        translate,
        "get_video_info",
        lambda video_id, api_key: {"duration_seconds": 120, "title": "Proxy Failure"},
    )

    def raise_caption_error(video_id, target_lang, api_key, **kwargs):
        raise RuntimeError("Malformed reply")

    monkeypatch.setattr(translate, "fetch_captions_via_api", raise_caption_error)
    monkeypatch.setattr(
        translate,
        "extract_audio",
        lambda url, video_id, proxy="": f"/tmp/subtrad/{video_id}.m4a",
    )
    monkeypatch.setattr(
        translate,
        "transcribe_audio_with_metadata",
        lambda audio_path: {
            "segments": [{"start": 0.0, "end": 1.5, "text": "Hello"}],
            "language": "en",
            "timings": {"preprocess_seconds": 0.12, "transcription_seconds": 0.41},
        },
    )
    monkeypatch.setattr(
        translate,
        "translate_subtitles_with_metadata",
        lambda subtitles, target_lang, api_key, source_lang=None: {
            "segments": [{"start": 0.0, "end": 1.5, "text": "Bonjour"}],
            "detected_language": source_lang,
            "translation_status": "translated",
        },
    )
    monkeypatch.setattr(
        translate,
        "cleanup_audio",
        lambda audio_path: cleanup_calls.append(audio_path),
    )

    response = client.post(
        "/api/translate",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "target_lang": "fr",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["source"] == "whisper_transcription"
    assert data["needs_transcription"] is True
    assert cleanup_calls == ["/tmp/subtrad/dQw4w9WgXcQ.m4a"]


def test_youtube_api_error_falls_back_to_502(monkeypatch) -> None:
    """YouTube API failure should return a clear error."""
    from backend.routers import translate

    def raise_api_error(video_id, api_key):
        raise RuntimeError("YouTube API error 403: Forbidden")

    monkeypatch.setattr(translate, "get_video_info", raise_api_error)

    response = client.post(
        "/api/translate",
        json={
            "url": "https://www.youtube.com/watch?v=jNQXAC9IVRw",
            "target_lang": "fr",
        },
    )

    assert response.status_code == 502
    assert "Video metadata lookup failed" in response.json()["detail"]


def test_tiktok_still_uses_ytdlp(monkeypatch) -> None:
    """TikTok should continue using yt-dlp, not YouTube API."""
    from backend.routers import translate

    monkeypatch.setattr(
        translate,
        "fetch_video_duration_seconds",
        lambda url, proxy="": 30,
    )
    monkeypatch.setattr(
        translate,
        "fetch_existing_subtitles",
        lambda url, proxy="": [{"start": "0.0", "end": "1.0", "text": "Hey"}],
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

    response = client.post(
        "/api/translate",
        json={
            "url": "https://www.tiktok.com/@user/video/1234567890",
            "target_lang": "fr",
        },
    )

    assert response.status_code == 200
    assert response.json()["platform"] == "tiktok"
