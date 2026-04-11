from __future__ import annotations

import time
from pathlib import Path

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

try:
    from backend.services.rapidapi_downloader import extract_audio_via_rapidapi
    from backend.services.warp_rotator import is_youtube_block, rotate_warp_ip
except ModuleNotFoundError:  # pragma: no cover
    from services.rapidapi_downloader import extract_audio_via_rapidapi
    from services.warp_rotator import is_youtube_block, rotate_warp_ip


TEMP_AUDIO_DIR = Path("/tmp/subtrad")
YOUTUBE_COOKIE_FILE = Path("/root/yt_cookies.txt")


def get_settings():
    try:
        from backend.config import get_settings as _get_settings
    except ModuleNotFoundError:  # pragma: no cover
        from config import get_settings as _get_settings
    return _get_settings()


def extract_audio(url: str, video_id: str, proxy: str = "") -> str:
    TEMP_AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    output_template = str(TEMP_AUDIO_DIR / f"{video_id}.%(ext)s")
    options = {
        "format": "bestaudio/best",
        "outtmpl": output_template,
        "username": "oauth2",
        "password": "",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "m4a",
                "preferredquality": "128",
            }
        ],
        "quiet": True,
        "no_warnings": True,
        "extractor_args": {"youtube": {"player_client": ["web", "default"]}},
    }
    if YOUTUBE_COOKIE_FILE.exists():
        age_days = (time.time() - YOUTUBE_COOKIE_FILE.stat().st_mtime) / 86400
        if age_days < 30:
            options["cookiefile"] = str(YOUTUBE_COOKIE_FILE)
    if proxy:
        options["proxy"] = proxy

    def _extract() -> None:
        with YoutubeDL(options) as ydl:
            ydl.extract_info(url, download=True)

    try:
        _extract()
    except DownloadError as exc:
        if not is_youtube_block(exc):
            raise
        rotation_url = get_settings().warp_rotation_url
        if rotation_url:
            rotate_warp_ip(rotation_url)
        try:
            _extract()
        except DownloadError as retry_exc:
            if not is_youtube_block(retry_exc):
                raise
            return extract_audio_via_rapidapi(url)

    candidates = sorted(TEMP_AUDIO_DIR.glob(f"{video_id}.*"))
    if not candidates:
        raise FileNotFoundError(f"Audio file was not created for {video_id}")
    audio_path = candidates[0]

    return str(audio_path)


def cleanup_audio(path: str) -> None:
    Path(path).unlink(missing_ok=True)
