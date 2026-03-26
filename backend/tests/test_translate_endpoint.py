from fastapi.testclient import TestClient

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


def test_translate_returns_premium_redirect_for_long_videos(monkeypatch) -> None:
    from backend.routers import translate

    monkeypatch.setattr(
        translate,
        "fetch_video_duration_seconds",
        lambda url, proxy="": 721,
    )

    response = client.post(
        "/api/translate",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "target_lang": "fr",
        },
    )

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Video exceeds maximum duration",
        "redirect": "premium",
        "duration_seconds": 721,
    }


def test_translate_returns_clear_error_when_metadata_lookup_fails(monkeypatch) -> None:
    from backend.routers import translate

    def raise_metadata_error(url: str, proxy: str = "") -> int:
        raise RuntimeError("Metadata lookup blocked")

    monkeypatch.setattr(translate, "fetch_video_duration_seconds", raise_metadata_error)

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

    subtitles = [{"start": "00:00:01,000", "end": "00:00:02,000", "text": "Hello"}]
    monkeypatch.setattr(
        translate,
        "fetch_video_duration_seconds",
        lambda url, proxy="": 120,
    )
    monkeypatch.setattr(
        translate,
        "fetch_existing_subtitles",
        lambda url, proxy="": subtitles,
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
    assert response.json() == {
        "platform": "youtube",
        "video_id": "dQw4w9WgXcQ",
        "subtitles": [{"start": "00:00:01,000", "end": "00:00:02,000", "text": "Bonjour"}],
        "duration_seconds": 120,
        "needs_transcription": False,
        "source": "existing_captions",
        "target_lang": "fr",
        "detected_language": "en",
        "translation_status": "translated",
    }


def test_translate_runs_whisper_fallback_when_subtitles_are_missing(monkeypatch) -> None:
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
        lambda audio_path, api_key: {
            "segments": [{"start": 0.0, "end": 1.5, "text": "Hello world"}],
            "language": "en",
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
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "target_lang": "ja",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "platform": "youtube",
        "video_id": "dQw4w9WgXcQ",
        "subtitles": [{"start": 0.0, "end": 1.5, "text": "Bonjour le monde"}],
        "duration_seconds": 120,
        "needs_transcription": True,
        "source": "whisper_transcription",
        "target_lang": "ja",
        "detected_language": "en",
        "translation_status": "translated",
    }
    assert cleanup_calls == ["/tmp/subtrad/dQw4w9WgXcQ.m4a"]


def test_translate_returns_clear_error_when_transcription_fails(monkeypatch) -> None:
    from backend.routers import translate

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

    def raise_transcription_error(audio_path: str, api_key: str) -> dict[str, object]:
        raise RuntimeError("Whisper API unavailable")

    monkeypatch.setattr(
        translate,
        "transcribe_audio_with_metadata",
        raise_transcription_error,
    )

    response = client.post(
        "/api/translate",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "target_lang": "ja",
        },
    )

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Transcription pipeline failed",
        "error": "Whisper API unavailable",
    }
    assert cleanup_calls == ["/tmp/subtrad/dQw4w9WgXcQ.m4a"]


def test_translate_returns_skipped_status_when_source_matches_target(monkeypatch) -> None:
    from backend.routers import translate

    monkeypatch.setattr(translate, "fetch_video_duration_seconds", lambda url, proxy="": 120)
    monkeypatch.setattr(
        translate,
        "fetch_existing_subtitles",
        lambda url, proxy="": [{"start": "00:00:01,000", "end": "00:00:02,000", "text": "Hello"}],
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

    original_subtitles = [{"start": "00:00:01,000", "end": "00:00:02,000", "text": "Hello"}]
    monkeypatch.setattr(translate, "fetch_video_duration_seconds", lambda url, proxy="": 120)
    monkeypatch.setattr(translate, "fetch_existing_subtitles", lambda url, proxy="": original_subtitles)
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
    monkeypatch.setattr(translate, "fetch_video_duration_seconds", lambda url, proxy="": 120)
    monkeypatch.setattr(translate, "fetch_existing_subtitles", lambda url, proxy="": None)
    monkeypatch.setattr(
        translate,
        "extract_audio",
        lambda url, video_id, proxy="": f"/tmp/subtrad/{video_id}.m4a",
    )
    monkeypatch.setattr(
        translate,
        "transcribe_audio_with_metadata",
        lambda audio_path, api_key: {
            "segments": [{"start": 0.0, "end": 1.5, "text": "Hello world"}],
            "language": "en",
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
    monkeypatch.setattr(translate, "cleanup_audio", lambda audio_path: None)

    response = client.post(
        "/api/translate",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "target_lang": "fr",
        },
    )

    assert response.status_code == 200
    assert response.json()["translation_status"] == "translated"
    assert response.json()["needs_transcription"] is True
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
    monkeypatch.setattr(translate, "fetch_video_duration_seconds", lambda url, proxy="": 120)
    monkeypatch.setattr(
        translate,
        "fetch_existing_subtitles",
        lambda url, proxy="": [{"start": "00:00:01,000", "end": "00:00:02,000", "text": "Hello"}],
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
