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


def test_translate_returns_existing_subtitles(monkeypatch) -> None:
    from backend.routers import translate

    monkeypatch.setattr(
        translate,
        "fetch_video_duration_seconds",
        lambda url: 120,
    )
    monkeypatch.setattr(
        translate,
        "fetch_existing_subtitles",
        lambda url: [{"start": "00:00:01,000", "end": "00:00:02,000", "text": "Bonjour"}],
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
    }


def test_translate_marks_transcription_when_subtitles_are_missing(monkeypatch) -> None:
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
        "subtitles": [],
        "duration_seconds": 120,
        "needs_transcription": True,
    }
