from pathlib import Path

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
