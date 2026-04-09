from types import SimpleNamespace
import logging

import pytest
from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)

PLATFORM_CASES = [
    ("instagram", "https://www.instagram.com/reel/C7Dxyz12345/"),
    ("tiktok", "https://www.tiktok.com/@user/video/1234567890"),
]


@pytest.mark.parametrize(("platform", "url"), PLATFORM_CASES)
def test_ytdlp_happy_path_returns_transcript_exports(monkeypatch, platform: str, url: str) -> None:
    from backend.routers import translate

    translate_calls: list[dict[str, object]] = []

    monkeypatch.setattr(translate, "fetch_video_duration_seconds", lambda candidate_url, proxy="": 120)
    monkeypatch.setattr(translate, "fetch_existing_subtitles", lambda candidate_url, proxy="": None)
    monkeypatch.setattr(
        translate,
        "extract_audio",
        lambda candidate_url, video_id, proxy="": f"/tmp/subtrad/{video_id}.m4a",
    )
    monkeypatch.setattr(
        translate,
        "transcribe_audio_with_metadata",
        lambda audio_path: {
            "segments": [
                {"start": 0.0, "end": 1.5, "text": "Hello"},
                {"start": 31.0, "end": 33.0, "text": "world"},
            ],
            "language": "en",
        },
    )

    def fake_translate(subtitles, target_lang, api_key, source_lang=None):
        translate_calls.append(
            {
                "subtitles": subtitles,
                "target_lang": target_lang,
                "source_lang": source_lang,
            }
        )
        return {
            "segments": [
                {"start": 0.0, "end": 1.5, "text": "Bonjour"},
                {"start": 31.0, "end": 33.0, "text": "le monde"},
            ],
            "detected_language": "en",
            "translation_status": "translated",
        }

    monkeypatch.setattr(translate, "translate_subtitles_with_metadata", fake_translate)
    monkeypatch.setattr(translate, "cleanup_audio", lambda audio_path: None)

    response = client.post("/api/translate", json={"url": url, "target_lang": "fr"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["platform"] == platform
    assert payload["source"] == "whisper_transcription"
    assert payload["needs_transcription"] is True
    assert payload["translation_status"] == "translated"
    assert payload["exports"]["vtt"].startswith("WEBVTT")
    assert payload["exports"]["txt"] == "Hello\nworld"
    assert "platform: " + platform in payload["exports"]["md"]
    assert translate_calls == [
        {
            "subtitles": [
                {"start": 0.0, "end": 1.5, "text": "Hello"},
                {"start": 31.0, "end": 33.0, "text": "world"},
            ],
            "target_lang": "fr",
            "source_lang": "en",
        }
    ]


@pytest.mark.parametrize(("platform", "url"), PLATFORM_CASES)
def test_ytdlp_logs_whisper_timing_breakdown(monkeypatch, caplog, platform: str, url: str) -> None:
    from backend.routers import translate

    caplog.set_level(logging.INFO)

    monkeypatch.setattr(translate, "fetch_video_duration_seconds", lambda candidate_url, proxy="": 120)
    monkeypatch.setattr(translate, "fetch_existing_subtitles", lambda candidate_url, proxy="": None)
    monkeypatch.setattr(
        translate,
        "extract_audio",
        lambda candidate_url, video_id, proxy="": f"/tmp/subtrad/{video_id}.m4a",
    )
    monkeypatch.setattr(
        translate,
        "transcribe_audio_with_metadata",
        lambda audio_path: {
            "segments": [{"start": 0.0, "end": 1.5, "text": "Hello"}],
            "language": "en",
            "timings": {"preprocess_seconds": 0.11, "transcription_seconds": 0.42},
        },
    )
    monkeypatch.setattr(
        translate,
        "translate_subtitles_with_metadata",
        lambda subtitles, target_lang, api_key, source_lang=None: {
            "segments": [{"start": 0.0, "end": 1.5, "text": "Bonjour"}],
            "detected_language": "en",
            "translation_status": "translated",
        },
    )
    monkeypatch.setattr(translate, "cleanup_audio", lambda audio_path: None)

    response = client.post("/api/translate", json={"url": url, "target_lang": "fr"})

    assert response.status_code == 200
    assert "download_seconds" in caplog.text
    assert "preprocess_seconds" in caplog.text
    assert "transcription_seconds" in caplog.text
    assert "total_seconds" in caplog.text


@pytest.mark.parametrize(("platform", "url"), PLATFORM_CASES)
def test_ytdlp_returns_422_when_audio_extraction_fails(monkeypatch, platform: str, url: str) -> None:
    from backend.routers import translate

    monkeypatch.setattr(translate, "fetch_video_duration_seconds", lambda candidate_url, proxy="": 120)
    monkeypatch.setattr(translate, "fetch_existing_subtitles", lambda candidate_url, proxy="": None)
    monkeypatch.setattr(
        translate,
        "extract_audio",
        lambda candidate_url, video_id, proxy="": (_ for _ in ()).throw(RuntimeError("ffmpeg failed")),
    )

    response = client.post("/api/translate", json={"url": url, "target_lang": "fr"})

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Could not extract audio from this video.",
        "error_code": "audio_extraction_failed",
    }


@pytest.mark.parametrize(("platform", "url"), PLATFORM_CASES)
def test_ytdlp_returns_422_when_transcription_fails(monkeypatch, platform: str, url: str) -> None:
    from backend.routers import translate

    settings = translate.get_settings().model_copy(update={"openai_api_key": "test-openai-key"})

    class FakeSubtitleCache:
        def retrieve(self, video_id: str, target_lang: str):
            return None

        def store(self, video_id: str, target_lang: str, response_data: dict[str, object]) -> None:
            return None

    class FakeRequestCounter:
        def increment(self, video_id: str, target_lang: str) -> int:
            return 1

        def should_cache(self, video_id: str, target_lang: str) -> bool:
            return False

    monkeypatch.setattr(translate, "fetch_video_duration_seconds", lambda candidate_url, proxy="": 120)
    monkeypatch.setattr(translate, "fetch_existing_subtitles", lambda candidate_url, proxy="": None)
    monkeypatch.setattr(
        translate,
        "extract_audio",
        lambda candidate_url, video_id, proxy="": f"/tmp/subtrad/{video_id}.m4a",
    )
    monkeypatch.setattr(
        translate,
        "transcribe_audio_with_metadata",
        lambda audio_path: (_ for _ in ()).throw(ValueError("Audio preprocessing failed: invalid header")),
    )
    monkeypatch.setattr(translate, "cleanup_audio", lambda audio_path: None)

    with pytest.raises(translate.ApiError) as exc_info:
        translate._handle_ytdlp(
            url=url,
            platform=platform,
            video_id="test-video-id",
            target_lang="fr",
            settings=settings,
            cache=FakeSubtitleCache(),
            counter=FakeRequestCounter(),
        )

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == {
        "detail": "Audio transcription failed.",
        "error_code": "audio_transcription_failed",
    }


@pytest.mark.parametrize(("platform", "url"), PLATFORM_CASES)
def test_ytdlp_handles_missing_segments_payload_without_crashing(monkeypatch, platform: str, url: str) -> None:
    from backend.routers import translate

    monkeypatch.setattr(translate, "fetch_video_duration_seconds", lambda candidate_url, proxy="": 120)
    monkeypatch.setattr(translate, "fetch_existing_subtitles", lambda candidate_url, proxy="": None)
    monkeypatch.setattr(
        translate,
        "extract_audio",
        lambda candidate_url, video_id, proxy="": f"/tmp/subtrad/{video_id}.m4a",
    )
    monkeypatch.setattr(translate, "transcribe_audio_with_metadata", lambda audio_path: {"language": "en"})
    monkeypatch.setattr(translate, "cleanup_audio", lambda audio_path: None)

    response = client.post("/api/translate", json={"url": url, "target_lang": "fr"})

    assert response.status_code == 422
    assert response.json()["error_code"] == "no_speech_detected"


@pytest.mark.parametrize(("platform", "url"), PLATFORM_CASES)
def test_ytdlp_returns_403_for_videos_exceeding_duration_limit(monkeypatch, platform: str, url: str) -> None:
    from backend.routers import translate

    monkeypatch.setattr(translate, "fetch_video_duration_seconds", lambda candidate_url, proxy="": 18_001)

    response = client.post("/api/translate", json={"url": url, "target_lang": "fr"})

    assert response.status_code == 403
    assert response.json() == {
        "detail": "Video exceeds maximum duration",
        "redirect": "premium",
        "duration_seconds": 18_001,
    }


@pytest.mark.parametrize(("platform", "url"), PLATFORM_CASES)
def test_ytdlp_existing_captions_still_translate_when_target_language_matches(
    monkeypatch,
    platform: str,
    url: str,
) -> None:
    from backend.routers import translate

    translate_calls: list[dict[str, object]] = []
    settings = translate.get_settings().model_copy(update={"openai_api_key": "test-openai-key"})
    video_id = "C7Dxyz12345" if platform == "instagram" else "1234567890"

    monkeypatch.setattr(translate, "fetch_video_duration_seconds", lambda candidate_url, proxy="": 55)
    monkeypatch.setattr(
        translate,
        "fetch_existing_subtitles",
        lambda candidate_url, proxy="": [{"start": "0.0", "end": "1.0", "text": "Bonjour"}],
    )

    def fake_translate(subtitles, target_lang, api_key, source_lang=None):
        translate_calls.append(
            {
                "subtitles": subtitles,
                "target_lang": target_lang,
                "source_lang": source_lang,
            }
        )
        return {
            "segments": [{"start": "0.0", "end": "1.0", "text": "Bonjour traduit"}],
            "detected_language": "fr",
            "translation_status": "translated",
        }

    monkeypatch.setattr(translate, "translate_subtitles_with_metadata", fake_translate)

    response = translate._handle_ytdlp(
        url=url,
        platform=platform,
        video_id=video_id,
        target_lang="fr",
        settings=settings,
        cache=SimpleNamespace(store=lambda *args, **kwargs: None),
        counter=SimpleNamespace(
            increment=lambda *args, **kwargs: 1,
            should_cache=lambda *args, **kwargs: False,
        ),
    )

    payload = response.model_dump()
    assert payload["translation_status"] == "translated"
    assert payload["exports"] == {
        "vtt": "WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nBonjour traduit\n",
        "txt": "Bonjour traduit",
        "md": (
            "---\n"
            f"title: {platform}-{video_id}\n"
            f"platform: {platform}\n"
            f"video_id: {video_id}\n"
            "language: fr\n"
            f"date: {__import__('datetime').date.today().isoformat()}\n"
            "---\n\n"
            "[00:00] Bonjour traduit"
        ),
    }
    assert translate_calls == [
        {
            "subtitles": [{"start": "0.0", "end": "1.0", "text": "Bonjour"}],
            "target_lang": "fr",
            "source_lang": None,
        }
    ]


@pytest.mark.parametrize(("platform", "url"), PLATFORM_CASES)
def test_ytdlp_returns_422_when_platform_access_fails(monkeypatch, platform: str, url: str) -> None:
    from backend.routers import translate

    monkeypatch.setattr(
        translate,
        "fetch_video_duration_seconds",
        lambda candidate_url, proxy="": (_ for _ in ()).throw(RuntimeError("HTTP Error 429: Too Many Requests")),
    )
    monkeypatch.setattr(
        translate,
        "get_settings",
        lambda: SimpleNamespace(
            supported_languages=["fr", "es", "en", "ja"],
            cache_db_path="data/cache.db",
            cache_threshold=100,
            warp_proxy_url="",
            proxy_url="",
            warp_rotation_url="",
            openai_api_key="test-key",
        ),
    )

    response = client.post("/api/translate", json={"url": url, "target_lang": "fr"})

    assert response.status_code == 422
    assert response.json() == {
        "detail": "Could not access this video. It may be private or unavailable.",
        "error_code": "platform_access_failed",
    }


@pytest.mark.parametrize(("platform", "url"), PLATFORM_CASES)
def test_ytdlp_returns_422_when_whisper_detects_no_speech(monkeypatch, platform: str, url: str) -> None:
    from backend.routers import translate

    monkeypatch.setattr(translate, "fetch_video_duration_seconds", lambda candidate_url, proxy="": 120)
    monkeypatch.setattr(translate, "fetch_existing_subtitles", lambda candidate_url, proxy="": None)
    monkeypatch.setattr(
        translate,
        "extract_audio",
        lambda candidate_url, video_id, proxy="": f"/tmp/subtrad/{video_id}.m4a",
    )
    monkeypatch.setattr(
        translate,
        "transcribe_audio_with_metadata",
        lambda audio_path: {"segments": [], "language": "en"},
    )
    monkeypatch.setattr(translate, "cleanup_audio", lambda audio_path: None)

    response = client.post("/api/translate", json={"url": url, "target_lang": "fr"})

    assert response.status_code == 422
    assert response.json() == {
        "detail": "No speech detected in this video.",
        "error_code": "no_speech_detected",
    }


@pytest.mark.parametrize(("platform", "url"), PLATFORM_CASES)
def test_ytdlp_rotates_warp_and_retries_after_blocked_duration_lookup(
    monkeypatch,
    platform: str,
    url: str,
) -> None:
    from backend.routers import translate

    duration_attempts: list[str] = []
    rotation_calls: list[str] = []

    def fake_duration(candidate_url: str, proxy: str = "") -> int:
        duration_attempts.append(candidate_url)
        if len(duration_attempts) == 1:
            raise RuntimeError("HTTP Error 429: Too Many Requests")
        return 44

    monkeypatch.setattr(translate, "fetch_video_duration_seconds", fake_duration)
    monkeypatch.setattr(translate, "fetch_existing_subtitles", lambda candidate_url, proxy="": None)
    monkeypatch.setattr(
        translate,
        "extract_audio",
        lambda candidate_url, video_id, proxy="": f"/tmp/subtrad/{video_id}.m4a",
    )
    monkeypatch.setattr(
        translate,
        "transcribe_audio_with_metadata",
        lambda audio_path: {"segments": [{"start": 0.0, "end": 1.0, "text": "hello"}], "language": "en"},
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
    monkeypatch.setattr(translate, "cleanup_audio", lambda audio_path: None)
    monkeypatch.setattr(
        translate,
        "get_settings",
        lambda: SimpleNamespace(
            supported_languages=["fr", "es", "en", "ja"],
            cache_db_path="data/cache.db",
            cache_threshold=100,
            warp_proxy_url="",
            proxy_url="",
            warp_rotation_url="http://10.0.1.1:40002/rotate",
            openai_api_key="test-key",
        ),
    )
    monkeypatch.setattr(
        translate,
        "rotate_warp_ip",
        lambda rotation_url: rotation_calls.append(rotation_url) or True,
    )

    response = client.post("/api/translate", json={"url": url, "target_lang": "fr"})

    assert response.status_code == 200
    assert duration_attempts == [url, url]
    assert rotation_calls == ["http://10.0.1.1:40002/rotate"]


@pytest.mark.parametrize(("platform", "url"), PLATFORM_CASES)
def test_ytdlp_retries_even_when_warp_rotation_fails(monkeypatch, platform: str, url: str) -> None:
    from backend.routers import translate

    duration_attempts: list[str] = []
    rotation_calls: list[str] = []

    def fake_duration(candidate_url: str, proxy: str = "") -> int:
        duration_attempts.append(candidate_url)
        if len(duration_attempts) == 1:
            raise RuntimeError("HTTP Error 429: Too Many Requests")
        return 44

    monkeypatch.setattr(translate, "fetch_video_duration_seconds", fake_duration)
    monkeypatch.setattr(translate, "fetch_existing_subtitles", lambda candidate_url, proxy="": None)
    monkeypatch.setattr(
        translate,
        "extract_audio",
        lambda candidate_url, video_id, proxy="": f"/tmp/subtrad/{video_id}.m4a",
    )
    monkeypatch.setattr(
        translate,
        "transcribe_audio_with_metadata",
        lambda audio_path: {"segments": [{"start": 0.0, "end": 1.0, "text": "hello"}], "language": "en"},
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
    monkeypatch.setattr(translate, "cleanup_audio", lambda audio_path: None)
    monkeypatch.setattr(
        translate,
        "get_settings",
        lambda: SimpleNamespace(
            supported_languages=["fr", "es", "en", "ja"],
            cache_db_path="data/cache.db",
            cache_threshold=100,
            warp_proxy_url="",
            proxy_url="",
            warp_rotation_url="http://10.0.1.1:40002/rotate",
            openai_api_key="test-key",
        ),
    )
    monkeypatch.setattr(
        translate,
        "rotate_warp_ip",
        lambda rotation_url: rotation_calls.append(rotation_url) or False,
    )

    response = client.post("/api/translate", json={"url": url, "target_lang": "fr"})

    assert response.status_code == 200
    assert duration_attempts == [url, url]
    assert rotation_calls == ["http://10.0.1.1:40002/rotate"]
