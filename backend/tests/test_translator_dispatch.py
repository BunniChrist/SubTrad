from __future__ import annotations

from backend.services.translator_dispatch import (
    detect_source_language_dispatch,
    translate_subtitles_with_metadata_dispatch,
)


def test_dispatch_routes_detection_to_openai_backend(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.services.translator_dispatch.detect_source_language",
        lambda segments, api_key: "en",
    )
    monkeypatch.setattr(
        "backend.services.translator_dispatch.detect_source_language_codex",
        lambda segments: "fr",
    )

    detected = detect_source_language_dispatch(
        [{"start": 0.0, "end": 1.0, "text": "Hello"}],
        "test-api-key",
        backend="openai",
    )

    assert detected == "en"


def test_dispatch_routes_translation_to_codex_backend(monkeypatch) -> None:
    codex_calls: list[dict[str, object]] = []

    monkeypatch.setattr(
        "backend.services.translator_dispatch.translate_subtitles_with_metadata",
        lambda segments, target_lang, api_key, source_lang=None: None,
    )

    def fake_codex(segments, target_lang, source_lang=None):
        codex_calls.append(
            {
                "segments": segments,
                "target_lang": target_lang,
                "source_lang": source_lang,
            }
        )
        return {
            "segments": [{"start": 0.0, "end": 1.0, "text": "Bonjour"}],
            "detected_language": "en",
            "translation_status": "translated",
        }

    monkeypatch.setattr(
        "backend.services.translator_dispatch.translate_subtitles_with_metadata_codex",
        fake_codex,
    )

    result = translate_subtitles_with_metadata_dispatch(
        [{"start": 0.0, "end": 1.0, "text": "Hello"}],
        "fr",
        "test-api-key",
        source_lang="en",
        backend="codex",
    )

    assert result["translation_status"] == "translated"
    assert codex_calls == [
        {
            "segments": [{"start": 0.0, "end": 1.0, "text": "Hello"}],
            "target_lang": "fr",
            "source_lang": "en",
        }
    ]


def test_dispatch_uses_default_backend_from_settings(monkeypatch) -> None:
    monkeypatch.setattr(
        "backend.services.translator_dispatch.get_settings",
        lambda: type("Settings", (), {"translation_backend": "codex"})(),
    )
    monkeypatch.setattr(
        "backend.services.translator_dispatch.translate_subtitles_with_metadata",
        lambda segments, target_lang, api_key, source_lang=None: {
            "segments": segments,
            "detected_language": "en",
            "translation_status": "translated",
        },
    )
    monkeypatch.setattr(
        "backend.services.translator_dispatch.translate_subtitles_with_metadata_codex",
        lambda segments, target_lang, source_lang=None: {
            "segments": [{"start": 0.0, "end": 1.0, "text": "Bonjour"}],
            "detected_language": "en",
            "translation_status": "translated",
        },
    )

    result = translate_subtitles_with_metadata_dispatch(
        [{"start": 0.0, "end": 1.0, "text": "Hello"}],
        "fr",
        "test-api-key",
    )

    assert result["segments"] == [{"start": 0.0, "end": 1.0, "text": "Bonjour"}]
