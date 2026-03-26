from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


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
        lambda url: 721,
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

    def raise_metadata_error(url: str) -> int:
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
        lambda url: 120,
    )
    monkeypatch.setattr(
        translate,
        "fetch_existing_subtitles",
        lambda url: subtitles,
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
        lambda url: 120,
    )
    monkeypatch.setattr(
        translate,
        "fetch_existing_subtitles",
        lambda url: None,
    )
    monkeypatch.setattr(
        translate,
        "extract_audio",
        lambda url, video_id: f"/tmp/subtrad/{video_id}.m4a",
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

    monkeypatch.setattr(translate, "fetch_video_duration_seconds", lambda url: 120)
    monkeypatch.setattr(translate, "fetch_existing_subtitles", lambda url: None)
    monkeypatch.setattr(
        translate,
        "extract_audio",
        lambda url, video_id: f"/tmp/subtrad/{video_id}.m4a",
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

    monkeypatch.setattr(translate, "fetch_video_duration_seconds", lambda url: 120)
    monkeypatch.setattr(
        translate,
        "fetch_existing_subtitles",
        lambda url: [{"start": "00:00:01,000", "end": "00:00:02,000", "text": "Hello"}],
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
    monkeypatch.setattr(translate, "fetch_video_duration_seconds", lambda url: 120)
    monkeypatch.setattr(translate, "fetch_existing_subtitles", lambda url: original_subtitles)
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
