from pathlib import Path

import pytest

from backend.services.audio_extractor import cleanup_audio, extract_audio


def test_extract_audio_uses_first_rapidapi_provider(monkeypatch, tmp_path) -> None:
    from backend.services import audio_extractor

    rapidapi_audio = tmp_path / "rapidapi.m4a"
    rapidapi_audio.write_bytes(b"rapidapi-audio")
    calls: list[str] = []

    monkeypatch.setattr(
        audio_extractor,
        "extract_audio_via_rapidapi",
        lambda url: calls.append(url) or str(rapidapi_audio),
    )

    audio_path = extract_audio(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "dQw4w9WgXcQ",
    )

    assert audio_path == str(rapidapi_audio)
    assert calls == ["https://www.youtube.com/watch?v=dQw4w9WgXcQ"]


def test_extract_audio_keeps_legacy_signature_but_ignores_proxy(monkeypatch, tmp_path) -> None:
    from backend.services import audio_extractor

    rapidapi_audio = tmp_path / "rapidapi.m4a"
    rapidapi_audio.write_bytes(b"rapidapi-audio")

    monkeypatch.setattr(
        audio_extractor,
        "extract_audio_via_rapidapi",
        lambda url: str(rapidapi_audio),
    )

    audio_path = extract_audio(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "unused-video-id",
        proxy="socks5h://127.0.0.1:1",
    )

    assert audio_path == str(rapidapi_audio)


def test_extract_audio_raises_when_both_providers_fail(monkeypatch) -> None:
    from backend.services import audio_extractor

    monkeypatch.setattr(
        audio_extractor,
        "extract_audio_via_rapidapi",
        lambda url: (_ for _ in ()).throw(RuntimeError("all rapidapi providers failed")),
    )

    with pytest.raises(RuntimeError, match="all rapidapi providers failed"):
        extract_audio(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "dQw4w9WgXcQ",
        )


def test_cleanup_audio_removes_existing_file(tmp_path) -> None:
    audio_file = tmp_path / "sample.m4a"
    audio_file.write_bytes(b"fake-audio")

    cleanup_audio(str(audio_file))

    assert audio_file.exists() is False


def test_cleanup_audio_ignores_missing_file(tmp_path) -> None:
    missing_file = tmp_path / "missing.m4a"

    cleanup_audio(str(missing_file))

    assert missing_file.exists() is False


@pytest.mark.integration
def test_extract_audio_downloads_real_youtube_audio() -> None:
    from backend.config import get_settings

    settings = get_settings()
    if not settings.rapidapi_key or not settings.rapidapi_host_1:
        pytest.skip("RapidAPI integration environment is not configured")

    audio_path = extract_audio(
        "https://www.youtube.com/watch?v=jNQXAC9IVRw",
        "jNQXAC9IVRw",
    )

    try:
        assert Path(audio_path).exists()
        assert audio_path.endswith((".m4a", ".mp3", ".webm", ".mp4"))
    finally:
        cleanup_audio(audio_path)
