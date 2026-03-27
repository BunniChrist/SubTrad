from pathlib import Path
from types import SimpleNamespace

import pytest
from yt_dlp.utils import DownloadError

from backend.services.audio_extractor import cleanup_audio, extract_audio


class FakeYoutubeDL:
    def __init__(self, options: dict) -> None:
        self.options = options

    def __enter__(self) -> "FakeYoutubeDL":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def extract_info(self, url: str, download: bool) -> dict[str, str]:
        output_template = self.options["outtmpl"]
        target_path = Path(output_template.replace("%(ext)s", "m4a"))
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(b"fake-audio")
        return {"id": "dQw4w9WgXcQ", "ext": "m4a"}

    def prepare_filename(self, info: dict[str, str]) -> str:
        return self.options["outtmpl"].replace("%(ext)s", info["ext"])


def test_extract_audio_returns_existing_audio_file_path(monkeypatch) -> None:
    from backend.services import audio_extractor

    monkeypatch.setattr(audio_extractor, "YoutubeDL", FakeYoutubeDL)

    audio_path = extract_audio(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "dQw4w9WgXcQ",
    )

    try:
        assert audio_path.endswith((".mp3", ".m4a", ".webm"))
        assert Path(audio_path).exists()
    finally:
        cleanup_audio(audio_path)


def test_extract_audio_returns_postprocessed_m4a_file(monkeypatch, tmp_path) -> None:
    from backend.services import audio_extractor

    captured_options: dict[str, object] = {}

    class PostProcessedYoutubeDL:
        def __init__(self, options: dict[str, object]) -> None:
            captured_options.update(options)

        def __enter__(self) -> "PostProcessedYoutubeDL":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def extract_info(self, url: str, download: bool) -> dict[str, str]:
            target_path = tmp_path / "dQw4w9WgXcQ.m4a"
            target_path.write_bytes(b"fake-audio" * 256)
            return {"id": "dQw4w9WgXcQ", "ext": "webm"}

        def prepare_filename(self, info: dict[str, str]) -> str:
            return str(tmp_path / f"{info['id']}.{info['ext']}")

    monkeypatch.setattr(audio_extractor, "TEMP_AUDIO_DIR", tmp_path)
    monkeypatch.setattr(audio_extractor, "YoutubeDL", PostProcessedYoutubeDL)

    audio_path = extract_audio(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "dQw4w9WgXcQ",
    )

    assert audio_path == str(tmp_path / "dQw4w9WgXcQ.m4a")
    assert Path(audio_path).exists()
    assert captured_options["postprocessors"] == [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "m4a",
            "preferredquality": "128",
        }
    ]
    assert captured_options["extractor_args"] == {
        "youtube": {"player_client": ["web", "default"]}
    }


def test_extract_audio_skips_stale_cookie_file(monkeypatch, tmp_path) -> None:
    from backend.services import audio_extractor

    captured_options: dict[str, object] = {}
    cookie_file = tmp_path / "yt_cookies.txt"
    cookie_file.write_text("stale-cookie")

    class CookieAwareYoutubeDL(FakeYoutubeDL):
        def __init__(self, options: dict[str, object]) -> None:
            captured_options.update(options)
            super().__init__(options)

    monkeypatch.setattr(audio_extractor, "TEMP_AUDIO_DIR", tmp_path)
    monkeypatch.setattr(audio_extractor, "YOUTUBE_COOKIE_FILE", cookie_file)
    monkeypatch.setattr(audio_extractor, "YoutubeDL", CookieAwareYoutubeDL)
    monkeypatch.setattr(audio_extractor.time, "time", lambda: cookie_file.stat().st_mtime + (31 * 86400))

    audio_path = extract_audio(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "dQw4w9WgXcQ",
    )

    try:
        assert "cookiefile" not in captured_options
    finally:
        cleanup_audio(audio_path)


def test_cleanup_audio_removes_existing_file(tmp_path) -> None:
    audio_file = tmp_path / "sample.m4a"
    audio_file.write_bytes(b"fake-audio")

    cleanup_audio(str(audio_file))

    assert audio_file.exists() is False


def test_cleanup_audio_ignores_missing_file(tmp_path) -> None:
    missing_file = tmp_path / "missing.m4a"

    cleanup_audio(str(missing_file))

    assert missing_file.exists() is False


def test_extract_audio_retries_after_rotation(monkeypatch, tmp_path) -> None:
    from backend.services import audio_extractor

    rotation_calls: list[str] = []
    extract_attempts: list[str] = []

    class RetryYoutubeDL:
        def __init__(self, options: dict[str, object]) -> None:
            self.options = options

        def __enter__(self) -> "RetryYoutubeDL":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def extract_info(self, url: str, download: bool) -> dict[str, str]:
            extract_attempts.append(url)
            if len(extract_attempts) == 1:
                raise DownloadError("Sign in to confirm you're not a bot")
            target_path = tmp_path / "dQw4w9WgXcQ.m4a"
            target_path.write_bytes(b"fake-audio")
            return {"id": "dQw4w9WgXcQ", "ext": "m4a"}

    monkeypatch.setattr(audio_extractor, "TEMP_AUDIO_DIR", tmp_path)
    monkeypatch.setattr(audio_extractor, "YoutubeDL", RetryYoutubeDL)
    monkeypatch.setattr(audio_extractor, "get_settings", lambda: SimpleNamespace(
        warp_rotation_url="http://10.0.1.1:40002/rotate"
    ))
    monkeypatch.setattr(
        audio_extractor,
        "rotate_warp_ip",
        lambda url: rotation_calls.append(url) or True,
    )

    audio_path = extract_audio(
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "dQw4w9WgXcQ",
    )

    assert audio_path == str(tmp_path / "dQw4w9WgXcQ.m4a")
    assert extract_attempts == [
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    ]
    assert rotation_calls == ["http://10.0.1.1:40002/rotate"]


def test_extract_audio_raises_after_failed_retry(monkeypatch, tmp_path) -> None:
    from backend.services import audio_extractor

    extract_attempts: list[str] = []

    class RetryFailsYoutubeDL:
        def __init__(self, options: dict[str, object]) -> None:
            self.options = options

        def __enter__(self) -> "RetryFailsYoutubeDL":
            return self

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

        def extract_info(self, url: str, download: bool) -> dict[str, str]:
            extract_attempts.append(url)
            if len(extract_attempts) == 1:
                raise DownloadError("HTTP Error 429: Too Many Requests")
            raise DownloadError("HTTP Error 429: Too Many Requests")

    monkeypatch.setattr(audio_extractor, "TEMP_AUDIO_DIR", tmp_path)
    monkeypatch.setattr(audio_extractor, "YoutubeDL", RetryFailsYoutubeDL)
    monkeypatch.setattr(audio_extractor, "get_settings", lambda: SimpleNamespace(
        warp_rotation_url="http://10.0.1.1:40002/rotate"
    ))
    monkeypatch.setattr(audio_extractor, "rotate_warp_ip", lambda url: True)

    with pytest.raises(DownloadError, match="HTTP Error 429"):
        extract_audio(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "dQw4w9WgXcQ",
        )


@pytest.mark.integration
def test_extract_audio_downloads_real_youtube_audio() -> None:
    try:
        audio_path = extract_audio(
            "https://www.youtube.com/watch?v=jNQXAC9IVRw",
            "jNQXAC9IVRw",
        )
    except DownloadError as exc:
        if "not a bot" in str(exc).lower():
            pytest.skip("YouTube blocked the integration download with an anti-bot challenge")
        raise

    try:
        assert Path(audio_path).exists()
        assert audio_path.endswith((".m4a", ".mp3", ".webm"))
    finally:
        cleanup_audio(audio_path)
