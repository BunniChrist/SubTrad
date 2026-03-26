from __future__ import annotations

from pathlib import Path

from yt_dlp import YoutubeDL


TEMP_AUDIO_DIR = Path("/tmp/subtrad")
YOUTUBE_COOKIE_FILE = Path("/root/yt_cookies.txt")


def extract_audio(url: str, video_id: str) -> str:
    TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    output_template = str(TEMP_AUDIO_DIR / f"{video_id}.%(ext)s")
    options = {
        "format": "bestaudio[ext=m4a]/bestaudio/best",
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
    }
    if YOUTUBE_COOKIE_FILE.exists():
        options["cookiefile"] = str(YOUTUBE_COOKIE_FILE)

    with YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        audio_path = Path(ydl.prepare_filename(info))

    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file was not created for {video_id}")

    return str(audio_path)


def cleanup_audio(path: str) -> None:
    Path(path).unlink(missing_ok=True)
