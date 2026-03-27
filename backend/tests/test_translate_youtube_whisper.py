from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_youtube_uses_whisper_fallback_when_captions_are_missing(monkeypatch) -> None:
    from backend.routers import translate

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
        lambda audio_path, api_key: {
            "segments": [{"start": 0.0, "end": 1.5, "text": "Hello"}],
            "language": "en",
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
    assert response.json() == {
        "platform": "youtube",
        "video_id": "dQw4w9WgXcQ",
        "subtitles": [{"start": 0.0, "end": 1.5, "text": "Bonjour"}],
        "duration_seconds": 120,
        "needs_transcription": True,
        "source": "whisper_transcription",
        "target_lang": "fr",
        "detected_language": "en",
        "translation_status": "translated",
    }
    assert cleanup_calls == ["/tmp/subtrad/dQw4w9WgXcQ.m4a"]


def test_youtube_whisper_fallback_returns_502_on_failure(monkeypatch) -> None:
    from backend.routers import translate

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
        lambda audio_path, api_key: (_ for _ in ()).throw(RuntimeError("Whisper API unavailable")),
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

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Transcription pipeline failed",
        "error": "Whisper API unavailable",
    }
    assert cleanup_calls == ["/tmp/subtrad/dQw4w9WgXcQ.m4a"]


def test_youtube_whisper_fallback_cleans_up_audio_when_extraction_fails(monkeypatch) -> None:
    from backend.routers import translate

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

    def fake_extract_audio(url: str, video_id: str, proxy: str = "") -> str:
        cleanup_calls.append(f"extract:{video_id}")
        raise RuntimeError("Audio extraction failed")

    monkeypatch.setattr(translate, "extract_audio", fake_extract_audio)
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

    assert response.status_code == 502
    assert response.json() == {
        "detail": "Transcription pipeline failed",
        "error": "Audio extraction failed",
    }
    assert cleanup_calls == ["extract:dQw4w9WgXcQ"]
