import json
import logging

import pytest
from fastapi import HTTPException


class FakeSubtitleCache:
    def retrieve(self, video_id: str, target_lang: str):
        return None

    def store(self, video_id: str, target_lang: str, response_data: dict[str, object]) -> None:
        return None


class FakeRequestCounter:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def increment(self, video_id: str, target_lang: str) -> int:
        self.calls.append((video_id, target_lang))
        return len(self.calls)

    def should_cache(self, video_id: str, target_lang: str) -> bool:
        return False


def test_youtube_uses_whisper_fallback_when_captions_are_missing(monkeypatch, caplog) -> None:
    from backend.routers import translate

    cleanup_calls: list[str] = []
    settings = translate.get_settings().model_copy(update={"openai_api_key": "test-openai-key"})
    caplog.set_level(logging.INFO)

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
            "segments": [{"start": 0.0, "end": 2.5, "text": "Hello there"}],
            "language": "en",
            "timings": {"preprocess_seconds": 0.12, "transcription_seconds": 0.48},
        },
    )
    monkeypatch.setattr(
        translate,
        "translate_subtitles_with_metadata",
        lambda subtitles, target_lang, api_key, source_lang=None: {
            "segments": [{"start": 0.0, "end": 2.5, "text": "Bonjour"}],
            "detected_language": source_lang,
            "translation_status": "translated",
        },
    )
    monkeypatch.setattr(
        translate,
        "cleanup_audio",
        lambda audio_path: cleanup_calls.append(audio_path),
    )

    response = translate._handle_youtube(
        video_id="dQw4w9WgXcQ",
        target_lang="fr",
        settings=settings,
        cache=FakeSubtitleCache(),
        counter=FakeRequestCounter(),
    )

    assert response.model_dump() == {
        "platform": "youtube",
        "video_id": "dQw4w9WgXcQ",
        "subtitles": [{"start": 0.0, "end": 2.5, "text": "Bonjour"}],
        "duration_seconds": 120,
        "needs_transcription": True,
        "source": "whisper_transcription",
        "target_lang": "fr",
        "detected_language": "en",
        "translation_status": "translated",
        "exports": {
            "vtt": "WEBVTT\n\n00:00:00.000 --> 00:00:02.500\nHello there\n",
            "txt": "Hello there",
            "md": (
                "---\n"
                "title: youtube-dQw4w9WgXcQ\n"
                "platform: youtube\n"
                "video_id: dQw4w9WgXcQ\n"
                "language: en\n"
                "date: 2026-04-04\n"
                "---\n\n"
                "[00:00] Hello there"
            ),
        },
    }
    assert cleanup_calls == ["/tmp/subtrad/dQw4w9WgXcQ.m4a"]
    assert "download_seconds" in caplog.text
    assert "preprocess_seconds" in caplog.text
    assert "transcription_seconds" in caplog.text
    assert "total_seconds" in caplog.text


def test_youtube_whisper_fallback_raises_http_exception_on_failure(monkeypatch) -> None:
    from backend.routers import translate

    cleanup_calls: list[str] = []
    settings = translate.get_settings().model_copy(update={"openai_api_key": "test-openai-key"})

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
        lambda audio_path: (_ for _ in ()).throw(RuntimeError("Whisper API unavailable")),
    )
    monkeypatch.setattr(
        translate,
        "cleanup_audio",
        lambda audio_path: cleanup_calls.append(audio_path),
    )

    with pytest.raises(HTTPException) as exc_info:
        translate._handle_youtube(
            video_id="dQw4w9WgXcQ",
            target_lang="fr",
            settings=settings,
            cache=FakeSubtitleCache(),
            counter=FakeRequestCounter(),
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == {
        "detail": "Transcription pipeline failed.",
        "error_code": "internal_error",
    }
    assert cleanup_calls == ["/tmp/subtrad/dQw4w9WgXcQ.m4a"]


def test_youtube_whisper_fallback_cleans_up_audio_when_extraction_fails(monkeypatch) -> None:
    from backend.routers import translate

    cleanup_calls: list[str] = []
    settings = translate.get_settings().model_copy(update={"openai_api_key": "test-openai-key"})

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

    with pytest.raises(HTTPException) as exc_info:
        translate._handle_youtube(
            video_id="dQw4w9WgXcQ",
            target_lang="fr",
            settings=settings,
            cache=FakeSubtitleCache(),
            counter=FakeRequestCounter(),
        )

    assert exc_info.value.status_code == 500
    assert exc_info.value.detail == {
        "detail": "Transcription pipeline failed.",
        "error_code": "internal_error",
    }
    assert cleanup_calls == ["extract:dQw4w9WgXcQ"]


def test_youtube_raises_http_exception_when_duration_key_is_missing(monkeypatch) -> None:
    from backend.routers import translate

    settings = translate.get_settings().model_copy(update={"openai_api_key": "test-openai-key"})

    monkeypatch.setattr(
        translate,
        "get_video_info",
        lambda video_id, api_key: {"title": "Broken payload"},
    )

    with pytest.raises(HTTPException) as exc_info:
        translate._handle_youtube(
            video_id="dQw4w9WgXcQ",
            target_lang="fr",
            settings=settings,
            cache=FakeSubtitleCache(),
            counter=FakeRequestCounter(),
        )

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == {
        "detail": "Video metadata lookup failed",
        "error": "Missing video duration",
    }


def test_youtube_handles_polymorphic_translation_result_objects(monkeypatch) -> None:
    from backend.routers import translate

    settings = translate.get_settings().model_copy(update={"openai_api_key": "test-openai-key"})

    class TranslationResult:
        def __init__(self) -> None:
            self.segments = [{"start": 0.0, "end": 1.5, "text": "Bonjour"}]
            self.detected_language = "en"
            self.translation_status = "translated"

    monkeypatch.setattr(
        translate,
        "get_video_info",
        lambda video_id, api_key: {"duration_seconds": 120, "title": "No Subs"},
    )
    monkeypatch.setattr(translate, "fetch_captions_via_api", lambda video_id, target_lang, api_key, **kwargs: None)
    monkeypatch.setattr(
        translate,
        "extract_audio",
        lambda url, video_id, proxy="": f"/tmp/subtrad/{video_id}.m4a",
    )
    monkeypatch.setattr(
        translate,
        "transcribe_audio_with_metadata",
        lambda audio_path: {"segments": [{"start": 0.0, "end": 1.5, "text": "Hello"}], "language": "en"},
    )
    monkeypatch.setattr(translate, "translate_subtitles_with_metadata", lambda *args, **kwargs: TranslationResult())
    monkeypatch.setattr(translate, "cleanup_audio", lambda audio_path: None)

    response = translate._handle_youtube(
        video_id="dQw4w9WgXcQ",
        target_lang="fr",
        settings=settings,
        cache=FakeSubtitleCache(),
        counter=FakeRequestCounter(),
    )

    assert response.model_dump()["subtitles"] == [{"start": 0.0, "end": 1.5, "text": "Bonjour"}]
