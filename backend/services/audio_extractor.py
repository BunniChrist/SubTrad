from __future__ import annotations

import time
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
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "128",
            }
        ],
        "quiet": True,
        "no_warnings": True,
    }
    if YOUTUBE_COOKIE_FILE.exists():
        age_days = (time.time() - YOUTUBE_COOKIE_FILE.stat().st_mtime) / 86400
        if age_days < 30:
            options["cookiefile"] = str(YOUTUBE_COOKIE_FILE)

    with YoutubeDL(options) as ydl:
        ydl.extract_info(url, download=True)

    candidates = sorted(TEMP_AUDIO_DIR.glob(f"{video_id}.*"))
    if not candidates:
        raise FileNotFoundError(f"Audio file was not created for {video_id}")
    audio_path = candidates[0]

    return str(audio_path)


def cleanup_audio(path: str) -> None:
    Path(path).unlink(missing_ok=True)
