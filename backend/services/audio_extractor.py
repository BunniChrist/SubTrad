from __future__ import annotations

from pathlib import Path

try:
    from backend.services.rapidapi_downloader import extract_audio_via_rapidapi
except ModuleNotFoundError:  # pragma: no cover
    from services.rapidapi_downloader import extract_audio_via_rapidapi


def extract_audio(url: str, video_id: str, proxy: str = "") -> str:
    # Keep the legacy signature for callers. Audio extraction is now RapidAPI-only.
    del video_id
    del proxy
    return extract_audio_via_rapidapi(url)


def cleanup_audio(path: str) -> None:
    Path(path).unlink(missing_ok=True)
